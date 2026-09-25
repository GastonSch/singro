from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncIterator

from ..audio.base import SAMPLE_RATE, SAMPLE_WIDTH
from ..translate import Translator, get_translator
from .base import CaptionEvent, Emit, Engine

log = logging.getLogger(__name__)


class LocalWhisperEngine(Engine):
    """100% offline engine: faster-whisper (CTranslate2, int8) for transcription
    and argostranslate for translation. Requires requirements-local.txt."""

    name = "local"

    def __init__(self, settings, model_size: str | None = None, compute_type: str = "int8") -> None:  # noqa: ANN001
        super().__init__(settings)
        self.model_size = model_size or os.getenv("WHISPER_MODEL", "small")
        self.compute_type = compute_type
        self._model = None
        self._lock = asyncio.Lock()
        self._translator: Translator | None = None

    def _ensure_model(self) -> None:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_size, device="cpu", compute_type=self.compute_type)

    def _transcribe(self, samples, source_language: str | None):  # noqa: ANN001
        segments, info = self._model.transcribe(
            samples,
            language=source_language,
            beam_size=1,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, getattr(info, "language", source_language)

    async def _process(
        self,
        pcm: bytes,
        emit: Emit,
        source_language: str | None,
        target_language: str,
    ) -> None:
        import numpy as np

        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        loop = asyncio.get_running_loop()
        async with self._lock:
            try:
                text, detected = await loop.run_in_executor(
                    None, self._transcribe, samples, source_language
                )
            except Exception as exc:
                log.exception("local transcription failed")
                await emit(CaptionEvent(kind="error", detail=f"local: {exc}"))
                return

        if not text:
            return

        detected = detected or source_language or ""
        translation = text
        if detected.lower() != target_language.lower():
            if self._translator is None:
                self._translator = get_translator()
            if self._translator is not None:
                try:
                    translation = await loop.run_in_executor(
                        None, self._translator.translate, text, detected, target_language
                    )
                except Exception as exc:
                    log.warning("local translation failed: %s", exc)
                    translation = ""
            else:
                translation = ""

        await emit(
            CaptionEvent(
                kind="block",
                original=text,
                translation=translation,
                final=True,
                source_language=detected or None,
            )
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
        self._ensure_model()
        chunk_bytes = max(SAMPLE_WIDTH, int(SAMPLE_RATE * SAMPLE_WIDTH * self.settings.chunk_seconds))
        overlap_bytes = max(0, int(SAMPLE_RATE * SAMPLE_WIDTH * self.settings.overlap_seconds))
        buffer = bytearray()
        async for data in audio:
            buffer.extend(data)
            if len(buffer) < chunk_bytes:
                continue
            window = bytes(buffer)
            buffer = bytearray(buffer[-overlap_bytes:]) if overlap_bytes else bytearray()
            await self._process(window, emit, source_language, target_language)
        if buffer:
            await self._process(bytes(buffer), emit, source_language, target_language)
