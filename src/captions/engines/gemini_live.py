from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from .base import CaptionEvent, Emit, Engine, interpreter_instruction

log = logging.getLogger(__name__)


class GeminiLiveEngine(Engine):
    """Lowest-latency engine using the Gemini Live API (bidirectional streaming).

    The input transcription gives the original language, while the model turn is
    instructed to emit only the translation. A long talk is transparently
    reconnected when the server closes the session.
    """

    name = "gemini_live"

    def __init__(self, settings) -> None:  # noqa: ANN001
        super().__init__(settings)
        from google import genai

        if not settings.api_key:
            raise RuntimeError("Falta GEMINI_API_KEY para el motor gemini_live")
        self.client = genai.Client(api_key=settings.api_key)

    def _config(self, source_language: str | None, target_language: str):  # noqa: ANN202
        from google.genai import types

        if source_language:
            transcription = types.AudioTranscriptionConfig(language_codes=[source_language])
        else:
            transcription = types.AudioTranscriptionConfig()

        kwargs = {
            "response_modalities": ["AUDIO"] if self.settings.native_translation else ["TEXT"],
            "system_instruction": types.Content(
                parts=[types.Part(text=interpreter_instruction(target_language, self.settings.glossary))]
            ),
            "input_audio_transcription": transcription,
            "realtime_input_config": types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    silence_duration_ms=self.settings.vad_silence_ms,
                    prefix_padding_ms=100,
                )
            ),
        }
        if self.settings.thinking_level:
            try:
                kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level=self.settings.thinking_level
                )
            except Exception:  # noqa: BLE001 - optional field
                log.debug("thinking_level no soportado, se ignora")
        if self.settings.native_translation:
            kwargs["translation_config"] = types.TranslationConfig(target_language_code=target_language)
            kwargs["output_audio_transcription"] = types.AudioTranscriptionConfig()
        return types.LiveConnectConfig(**kwargs)

    async def _session_once(
        self,
        audio_q: asyncio.Queue,
        emit: Emit,
        source_language: str | None,
        target_language: str,
    ) -> None:
        from google.genai import types

        translation_buffer = ""
        finished = asyncio.Event()
        input_done = asyncio.Event()
        loop = asyncio.get_running_loop()
        state: dict = {"input": "", "output": "", "language": None, "updated": 0.0}

        def merge_text(previous: str, chunk: str) -> str:
            if not chunk:
                return previous
            if not previous:
                return chunk
            if chunk in previous:
                return previous
            stripped = chunk.lstrip()
            if previous.rstrip().endswith(stripped):
                return previous
            if stripped and stripped.startswith(previous.strip()):
                return chunk
            return previous + chunk

        async def finalize() -> None:
            nonlocal translation_buffer
            if self.settings.native_translation:
                original, translation, language = state["input"], state["output"], state["language"]
                state["input"], state["output"], state["language"] = "", "", None
                state["updated"] = 0.0
                if original:
                    await emit(
                        CaptionEvent(
                            kind="caption", lane="original", text=original, final=True,
                            source_language=language,
                        )
                    )
                if translation:
                    await emit(
                        CaptionEvent(kind="caption", lane="translation", text=translation, final=True)
                    )
            elif translation_buffer.strip():
                text = translation_buffer.strip()
                translation_buffer = ""
                state["updated"] = 0.0
                await emit(CaptionEvent(kind="caption", lane="translation", text=text, final=True))

        async with self.client.aio.live.connect(
            model=self.settings.model, config=self._config(source_language, target_language)
        ) as session:

            async def feeder() -> None:
                try:
                    while True:
                        chunk = await audio_q.get()
                        if chunk is None:
                            return
                        await session.send_realtime_input(
                            audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("gemini_live feeder error")
                finally:
                    input_done.set()

            async def receiver() -> None:
                nonlocal translation_buffer
                try:
                    async for message in session.receive():
                        content = message.server_content
                        if content is None:
                            continue

                        original = content.input_transcription
                        if original and original.text:
                            state["input"] = merge_text(state["input"], original.text)
                            state["language"] = original.language_code or state["language"]
                            state["updated"] = loop.time()
                            await emit(
                                CaptionEvent(
                                    kind="caption",
                                    lane="original",
                                    text=state["input"],
                                    final=False,
                                    source_language=state["language"],
                                )
                            )
                        interim = content.interim_input_transcription
                        if interim and interim.text:
                            state["updated"] = loop.time()
                            await emit(
                                CaptionEvent(kind="caption", lane="original", text=interim.text, final=False)
                            )

                        if self.settings.native_translation:
                            output = content.output_transcription
                            if output and output.text:
                                state["output"] = merge_text(state["output"], output.text)
                                state["updated"] = loop.time()
                                await emit(
                                    CaptionEvent(
                                        kind="caption",
                                        lane="translation",
                                        text=state["output"],
                                        final=False,
                                    )
                                )
                        else:
                            if content.model_turn and content.model_turn.parts:
                                for part in content.model_turn.parts:
                                    text = getattr(part, "text", None)
                                    if text:
                                        translation_buffer += text
                                        state["updated"] = loop.time()
                                        await emit(
                                            CaptionEvent(
                                                kind="caption",
                                                lane="translation",
                                                text=translation_buffer.strip(),
                                                final=False,
                                            )
                                        )
                        if content.turn_complete:
                            await finalize()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("gemini_live receiver error")
                finally:
                    finished.set()

            async def finalizer() -> None:
                idle = self.settings.idle_seconds
                while not finished.is_set():
                    await asyncio.sleep(0.3)
                    updated = state["updated"]
                    if not updated:
                        continue
                    gap = loop.time() - updated
                    text = (state["output"] or state["input"]).strip()
                    ends_sentence = bool(text) and text[-1] in ".!?…"
                    if gap > idle * 1.8 or (ends_sentence and gap > idle * 0.6):
                        await finalize()

            async def flusher() -> None:
                await input_done.wait()
                await asyncio.sleep(self.settings.flush_seconds)
                await finalize()
                finished.set()

            feeder_task = asyncio.create_task(feeder())
            receiver_task = asyncio.create_task(receiver())
            finalizer_task = asyncio.create_task(finalizer())
            flusher_task = asyncio.create_task(flusher())
            try:
                await finished.wait()
            finally:
                for task in (feeder_task, receiver_task, finalizer_task, flusher_task):
                    task.cancel()
                await asyncio.gather(
                    feeder_task, receiver_task, finalizer_task, flusher_task, return_exceptions=True
                )

    async def run(
        self,
        audio: AsyncIterator[bytes],
        emit: Emit,
        *,
        session_id: str,
        source_language: str | None,
        target_language: str,
    ) -> None:
        audio_q: asyncio.Queue = asyncio.Queue(maxsize=200)

        async def pump() -> None:
            try:
                async for chunk in audio:
                    await audio_q.put(chunk)
            finally:
                await audio_q.put(None)

        pump_task = asyncio.create_task(pump())
        backoff = 1.0
        try:
            while not (pump_task.done() and audio_q.empty()):
                try:
                    await self._session_once(audio_q, emit, source_language, target_language)
                    backoff = 1.0
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.exception("gemini_live session failed")
                    await emit(CaptionEvent(kind="error", detail=f"gemini_live: {exc}"))
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 15.0)
        finally:
            pump_task.cancel()
            await asyncio.gather(pump_task, return_exceptions=True)
