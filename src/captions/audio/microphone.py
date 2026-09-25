from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .base import BYTES_PER_SECOND, CHANNELS, SAMPLE_RATE, AudioSource


class MicrophoneAudioSource(AudioSource):
    """Live microphone capture via sounddevice/PortAudio.

    Requires: uv pip install -r requirements-mic.txt
    """

    def __init__(self, device: int | None = None, chunk_ms: int = 100) -> None:
        self.device = device
        self.chunk_ms = max(20, chunk_ms)

    async def stream(self) -> AsyncIterator[bytes]:
        try:
            import sounddevice as sd
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "El micrófono requiere sounddevice: uv pip install -r requirements-mic.txt"
            ) from exc

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        blocksize = max(1, int(SAMPLE_RATE * self.chunk_ms / 1000))

        def callback(indata, frames, time_info, status) -> None:  # noqa: ANN001
            loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=blocksize,
            device=self.device,
            callback=callback,
        )
        stream.start()
        try:
            while True:
                yield await queue.get()
        finally:
            stream.stop()
            stream.close()
