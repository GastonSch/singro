from __future__ import annotations

import asyncio
import logging
import shutil
import time
from typing import AsyncIterator

from .base import BYTES_PER_SECOND, SAMPLE_RATE, SAMPLE_WIDTH, AudioSource

log = logging.getLogger(__name__)


class FFmpegAudioSource(AudioSource):
    """Decodes a local file, an HTTP/HLS stream or an RTSP feed with ffmpeg.

    Emits real-time paced PCM chunks so the rest of the pipeline behaves like a
    live microphone, which is what a conference stream looks like.
    """

    def __init__(
        self,
        url: str,
        *,
        realtime: bool = True,
        loop: bool = False,
        chunk_ms: int = 100,
    ) -> None:
        self.url = url
        self.realtime = realtime
        self.loop = loop
        self.chunk_ms = max(20, chunk_ms)
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task | None = None

    def _command(self) -> list[str]:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg no está instalado o no está en el PATH")
        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            self.url,
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "pipe:1",
        ]

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            log.debug("ffmpeg[%s]: %s", self.url, line.decode(errors="replace").strip())

    async def stream(self) -> AsyncIterator[bytes]:
        chunk_bytes = max(
            SAMPLE_WIDTH, int(BYTES_PER_SECOND * self.chunk_ms / 1000)
        )
        while True:
            self._proc = await asyncio.create_subprocess_exec(
                *self._command(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._stderr_task = asyncio.create_task(self._drain_stderr(self._proc))
            started = time.monotonic()
            produced = 0
            try:
                assert self._proc.stdout is not None
                while True:
                    try:
                        data = await self._proc.stdout.readexactly(chunk_bytes)
                    except asyncio.IncompleteReadError as exc:
                        if exc.partial:
                            yield exc.partial
                        break
                    produced += len(data)
                    if self.realtime:
                        target = produced / BYTES_PER_SECOND
                        delay = target - (time.monotonic() - started)
                        if delay > 0:
                            await asyncio.sleep(delay)
                    yield data
            finally:
                await self.close()
            if not self.loop:
                break
            await asyncio.sleep(0.2)

    async def close(self) -> None:
        proc, self._proc = self._proc, None
        if self._stderr_task:
            self._stderr_task.cancel()
            self._stderr_task = None
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            except ProcessLookupError:
                pass
