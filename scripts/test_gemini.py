#!/usr/bin/env python
"""Prueba end-to-end de un motor Gemini con un audio del repo.

Uso:
    GEMINI_API_KEY=... .venv/bin/python scripts/test_gemini.py gemini_chunk samples/demo_en.mp3
    CAPTIONS_ENGINE=gemini_live .venv/bin/python scripts/test_gemini.py gemini_live samples/demo_es.mp3
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from captions.audio import build_source  # noqa: E402
from captions.config import Settings, SourceConfig, load_settings  # noqa: E402
from captions.engines import build_engine  # noqa: E402


async def main(engine_name: str, audio_path: str, source_language: str | None, target_language: str) -> None:
    base = load_settings()
    settings = Settings(
        api_key=base.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        engine=engine_name,
        model=base.model,
        rest_model=base.rest_model,
        chunk_seconds=4.0,
        overlap_seconds=0.5,
        native_translation=base.native_translation,
    )
    print(f"modelo: {settings.model} | native_translation: {settings.native_translation}")
    if not settings.api_key:
        raise SystemExit("Falta GEMINI_API_KEY / GOOGLE_API_KEY en el entorno")

    engine = build_engine(settings)
    source = build_source(SourceConfig(type="file", url=audio_path, realtime=True))
    started = time.monotonic()
    blocks = 0

    async def emit(event):  # noqa: ANN001
        nonlocal blocks
        elapsed = time.monotonic() - started
        if event.kind == "block":
            blocks += 1
            print(f"[{elapsed:5.1f}s] ORIGINAL : {event.original}")
            print(f"[{elapsed:5.1f}s] TRADUCC : {event.translation}")
            print("-" * 70)
        elif event.kind == "caption" and event.final and event.text:
            lane = event.lane.upper()
            print(f"[{elapsed:5.1f}s] {lane:<8}: {event.text}")
        elif event.kind == "error":
            print(f"[{elapsed:5.1f}s] ERROR    : {event.detail}")

    await engine.run(
        source.stream(),
        emit,
        session_id="test",
        source_language=source_language,
        target_language=target_language,
    )
    await engine.aclose()
    print(f"\nListo. {blocks} bloques traducidos en {time.monotonic() - started:.1f}s.")


if __name__ == "__main__":
    engine_name = sys.argv[1] if len(sys.argv) > 1 else "gemini_chunk"
    audio_path = sys.argv[2] if len(sys.argv) > 2 else "samples/demo_en.mp3"
    source_language = sys.argv[3] if len(sys.argv) > 3 else "en"
    target_language = sys.argv[4] if len(sys.argv) > 4 else "es"
    asyncio.run(main(engine_name, audio_path, source_language, target_language))
