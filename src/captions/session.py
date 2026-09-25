from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .audio import BYTES_PER_SECOND, build_source
from .config import SessionConfig, Settings
from .engines import CaptionEvent, Engine
from .events import EventBus

log = logging.getLogger(__name__)


class Session:
    """One audio source, one engine run, one caption stream."""

    def __init__(self, config: SessionConfig, engine: Engine, bus: EventBus, settings: Settings) -> None:
        self.config = config
        self.engine = engine
        self.bus = bus
        self.settings = settings
        self.id = config.id
        self.state = "idle"
        self.blocks: list[dict[str, Any]] = []
        self.stats: dict[str, Any] = {
            "captions": 0,
            "errors": 0,
            "segments": 0,
            "latency_ms": None,
            "started_at": None,
            "last_caption_at": None,
            "audio_seconds": 0.0,
        }
        self._source = None
        self._task: asyncio.Task | None = None
        self._live_original = ""
        self._live_translation = ""
        self._last_original = ""
        self._started_monotonic = 0.0

    # ------------------------------------------------------------------ public
    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.config.name,
            "state": self.state,
            "source": self.config.source.type,
            "source_url": self.config.source.url,
            "source_language": self.config.source_language,
            "target_language": self.config.target_language,
            "video": self.config.video,
            "stats": dict(self.stats),
        }

    async def start(self) -> None:
        if self.state in {"running", "starting"}:
            return
        self.state = "starting"
        self._started_monotonic = time.monotonic()
        self.stats["started_at"] = time.time()
        self._source = build_source(self.config.source)
        self._task = asyncio.create_task(self._run(), name=f"session:{self.id}")
        await self._publish_status()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._source:
            await self._source.close()
        self.state = "stopped"
        await self._publish_status()

    # ----------------------------------------------------------------- private
    async def _timed_stream(self):  # noqa: ANN202
        assert self._source is not None
        async for chunk in self._source.stream():
            self.stats["audio_seconds"] += len(chunk) / BYTES_PER_SECOND
            yield chunk

    async def _run(self) -> None:
        self.state = "running"
        await self._publish_status()

        async def emit(event: CaptionEvent) -> None:
            await self._handle(event)

        try:
            await self.engine.run(
                self._timed_stream(),
                emit,
                session_id=self.id,
                source_language=self.config.source_language,
                target_language=self.config.target_language,
            )
            self.state = "finished"
        except asyncio.CancelledError:
            self.state = "stopped"
            raise
        except Exception as exc:
            log.exception("session %s failed", self.id)
            self.stats["errors"] += 1
            self.state = "error"
            self.bus.publish({"type": "error", "session": self.id, "detail": str(exc)})
        finally:
            await self._publish_status()

    def _estimate_latency_ms(self) -> float | None:
        elapsed_ms = (time.monotonic() - self._started_monotonic) * 1000.0
        latency = elapsed_ms - self.stats["audio_seconds"] * 1000.0
        return latency if latency > 0 else None

    def _record_latency(self) -> None:
        latency = self._estimate_latency_ms()
        if latency is None:
            return
        previous = self.stats["latency_ms"]
        if previous is None:
            self.stats["latency_ms"] = round(latency, 1)
        else:
            self.stats["latency_ms"] = round(previous * 0.7 + latency * 0.3, 1)

    async def _handle(self, event: CaptionEvent) -> None:
        now = time.time()
        if event.kind == "error":
            self.stats["errors"] += 1
            self.bus.publish({"type": "error", "session": self.id, "detail": event.detail})
            await self._publish_status()
            return

        if event.kind == "block":
            original = event.original or self._live_original
            block = {"ts": now, "original": original, "translation": event.translation}
            self.blocks.append(block)
            self.stats["captions"] += 1
            self.stats["segments"] += 1
            self.stats["last_caption_at"] = now
            self._live_original = ""
            self._live_translation = ""
            self._record_latency()
            if original:
                self.bus.publish({"type": "caption", "session": self.id, "lane": "original", "text": original, "final": True, "ts": now})
            if event.translation:
                self.bus.publish({"type": "caption", "session": self.id, "lane": "translation", "text": event.translation, "final": True, "ts": now})
            self.bus.publish({"type": "block", "session": self.id, **block})
            await self._publish_status()
            return

        if event.lane == "original":
            self._live_original = event.text
            if event.final:
                self._last_original = event.text
        else:
            self._live_translation = event.text
            if event.final:
                block = {"ts": now, "original": self._last_original, "translation": event.text}
                self.blocks.append(block)
                self.stats["captions"] += 1
                self.stats["segments"] += 1
                self.stats["last_caption_at"] = now
                self._record_latency()
                self.bus.publish({"type": "block", "session": self.id, **block})
                await self._publish_status()
        self.bus.publish(
            {
                "type": "caption",
                "session": self.id,
                "lane": event.lane,
                "text": event.text,
                "final": event.final,
                "source_language": event.source_language,
                "ts": now,
            }
        )

    async def _publish_status(self) -> None:
        self.bus.publish({"type": "status", "session": self.id, "state": self.state, "stats": dict(self.stats)})
