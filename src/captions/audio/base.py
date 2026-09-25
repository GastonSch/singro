from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHANNELS = 1

BYTES_PER_SECOND = SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS


def pcm_seconds(pcm: bytes) -> float:
    return len(pcm) / BYTES_PER_SECOND


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


class AudioSource(ABC):
    """A source of 16 kHz mono signed-16-bit little-endian PCM."""

    @abstractmethod
    def stream(self) -> AsyncIterator[bytes]:
        ...

    async def close(self) -> None:
        return None
