from __future__ import annotations

from typing import AsyncIterator

from .base import CaptionEvent, Emit, Engine

DEMO_LINES = [
    ("Cloud native systems scale horizontally by design.", "Los sistemas nativos de la nube escalan horizontalmente por diseño."),
    ("We are running more than thirty sessions in parallel.", "Estamos ejecutando más de treinta sesiones en paralelo."),
    ("The transcription model detects the spoken language automatically.", "El modelo de transcripción detecta automáticamente el idioma hablado."),
    ("Latency stays under two seconds for every stage.", "La latencia se mantiene por debajo de dos segundos en cada escenario."),
    ("This demo works offline, without any API key.", "Esta demostración funciona sin conexión, sin ninguna clave de API."),
]


class MockEngine(Engine):
    """Deterministic engine for offline demos and tests. No network, no models."""

    name = "mock"

    async def run(
        self,
        audio: AsyncIterator[bytes],
        emit: Emit,
        *,
        session_id: str,
        source_language: str | None,
        target_language: str,
    ) -> None:
        index = 0
        chunks = 0
        async for _chunk in audio:
            chunks += 1
            if chunks % 25:  # ~every 2.5s of 100ms chunks
                continue
            original, translation = DEMO_LINES[index % len(DEMO_LINES)]
            index += 1
            await emit(
                CaptionEvent(
                    kind="block",
                    original=original,
                    translation=translation,
                    final=True,
                    source_language=source_language or "en",
                )
            )
