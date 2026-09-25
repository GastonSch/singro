from __future__ import annotations

from .base import CaptionEvent, Emit, Engine

__all__ = ["CaptionEvent", "Emit", "Engine", "build_engine"]


def build_engine(settings) -> Engine:  # noqa: ANN001
    name = (settings.engine or "gemini_live").lower()
    if name == "mock":
        from .mock import MockEngine

        return MockEngine(settings)
    if name == "gemini_live":
        from .gemini_live import GeminiLiveEngine

        return GeminiLiveEngine(settings)
    if name == "gemini_chunk":
        from .gemini_chunk import GeminiChunkEngine

        return GeminiChunkEngine(settings)
    if name == "local":
        from .local import LocalWhisperEngine

        return LocalWhisperEngine(settings)
    raise ValueError(f"Motor desconocido: {settings.engine!r}")
