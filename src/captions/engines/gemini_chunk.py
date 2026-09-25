from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from pydantic import BaseModel

from ..audio.base import SAMPLE_RATE, SAMPLE_WIDTH, pcm_to_wav
from .base import CaptionEvent, Emit, Engine, glossary_lines, language_name

log = logging.getLogger(__name__)


class CaptionPair(BaseModel):
    original: str
    translation: str


class GeminiChunkEngine(Engine):
    """Robust REST engine: slices audio in overlapping windows and asks Gemini for
    a JSON pair (original + translation). Simple to scale: every window is an
    independent, stateless request."""

    name = "gemini_chunk"

    def __init__(self, settings) -> None:  # noqa: ANN001
        super().__init__(settings)
        from google import genai

        if not settings.api_key:
            raise RuntimeError("Falta GEMINI_API_KEY para el motor gemini_chunk")
        self.client = genai.Client(api_key=settings.api_key)
        self.semaphore = asyncio.Semaphore(settings.max_inflight)
        self._last_original = ""

    def _prompt(self, source_language: str | None, target_language: str) -> str:
        target = language_name(target_language)
        hint = (
            f"The audio is in {language_name(source_language)}. "
            if source_language
            else "Detect the spoken language. "
        )
        return (
            "You are a real-time captioning and translation system for a live tech conference.\n"
            f"{hint}"
            "Respond ONLY with JSON with two fields:\n"
            '- "original": verbatim transcription in the spoken language.\n'
            f'- "translation": faithful {target} translation '
            f"(if the audio is already {target}, repeat it verbatim).\n"
            "Keep technical terms and proper nouns accurate. Never summarize or add commentary.\n"
            f"{glossary_lines(self.settings.glossary)}"
        )

    async def _process(
        self,
        pcm: bytes,
        emit: Emit,
        source_language: str | None,
        target_language: str,
    ) -> None:
        from google.genai import types

        async with self.semaphore:
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.settings.rest_model,
                    contents=[
                        types.Part.from_bytes(data=pcm_to_wav(pcm), mime_type="audio/wav"),
                        self._prompt(source_language, target_language),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CaptionPair,
                        temperature=0.0,
                    ),
                )
            except Exception as exc:
                log.exception("gemini_chunk request failed")
                await emit(CaptionEvent(kind="error", detail=f"gemini_chunk: {exc}"))
                return

            parsed = response.parsed
            if parsed is None:
                import json

                try:
                    parsed = CaptionPair(**json.loads(response.text or "{}"))
                except Exception:
                    return
            original = (parsed.original or "").strip()
            translation = (parsed.translation or "").strip()
            if not original and not translation:
                return
            if original and original == self._last_original:
                return
            self._last_original = original or self._last_original
            await emit(
                CaptionEvent(kind="block", original=original, translation=translation, final=True)
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
        chunk_bytes = max(SAMPLE_WIDTH, int(SAMPLE_RATE * SAMPLE_WIDTH * self.settings.chunk_seconds))
        overlap_bytes = max(0, int(SAMPLE_RATE * SAMPLE_WIDTH * self.settings.overlap_seconds))
        buffer = bytearray()
        tasks: list[asyncio.Task] = []
        async for data in audio:
            buffer.extend(data)
            if len(buffer) < chunk_bytes:
                continue
            window = bytes(buffer)
            buffer = bytearray(buffer[-overlap_bytes:]) if overlap_bytes else bytearray()
            tasks.append(
                asyncio.create_task(self._process(window, emit, source_language, target_language))
            )
        if buffer:
            tasks.append(
                asyncio.create_task(self._process(bytes(buffer), emit, source_language, target_language))
            )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
