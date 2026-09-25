from __future__ import annotations

from ..config import SourceConfig
from .base import BYTES_PER_SECOND, CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH, AudioSource, pcm_seconds, pcm_to_wav
from .ffmpeg import FFmpegAudioSource
from .microphone import MicrophoneAudioSource

__all__ = [
    "AudioSource",
    "BYTES_PER_SECOND",
    "CHANNELS",
    "FFmpegAudioSource",
    "MicrophoneAudioSource",
    "SAMPLE_RATE",
    "SAMPLE_WIDTH",
    "build_source",
    "pcm_seconds",
    "pcm_to_wav",
]


def build_source(config: SourceConfig) -> AudioSource:
    kind = (config.type or "file").lower()
    if kind in {"file", "stream", "url", "rtsp", "hls", "youtube"}:
        return FFmpegAudioSource(
            config.url,
            realtime=config.realtime,
            loop=config.loop,
            chunk_ms=config.chunk_ms,
        )
    if kind in {"mic", "microphone"}:
        return MicrophoneAudioSource(device=config.device, chunk_ms=config.chunk_ms)
    raise ValueError(f"Tipo de fuente desconocido: {config.type!r}")
