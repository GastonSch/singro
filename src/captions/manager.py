from __future__ import annotations

import logging

from .config import SessionConfig, Settings, SourceConfig
from .engines import Engine, build_engine
from .events import EventBus
from .session import Session

log = logging.getLogger(__name__)


class SessionManager:
    """Owns every session and the shared engines."""

    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self.sessions: dict[str, Session] = {}
        self._engine: Engine | None = None

    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = build_engine(self.settings)
        return self._engine

    async def load_configured(self) -> None:
        for config in self.settings.sessions:
            await self.add(config, start=self.settings.autostart)

    async def add(self, config: SessionConfig, start: bool = True) -> Session:
        if config.id in self.sessions:
            raise ValueError(f"La sesión {config.id!r} ya existe")
        session = Session(config, self.engine(), self.bus, self.settings)
        self.sessions[config.id] = session
        if start:
            await session.start()
        self.broadcast_sessions()
        return session

    async def remove(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session is None:
            raise KeyError(session_id)
        await session.stop()
        self.broadcast_sessions()

    async def start(self, session_id: str) -> None:
        await self.sessions[session_id].start()
        self.broadcast_sessions()

    async def stop(self, session_id: str) -> None:
        await self.sessions[session_id].stop()
        self.broadcast_sessions()

    def list(self) -> list[dict]:
        return [session.snapshot() for session in self.sessions.values()]

    def broadcast_sessions(self) -> None:
        self.bus.publish({"type": "sessions", "sessions": self.list()})

    def from_payload(self, payload: dict) -> SessionConfig:
        source = payload.get("source") or {}
        return SessionConfig(
            id=str(payload["id"]),
            name=str(payload.get("name", payload["id"])),
            source=SourceConfig(
                type=str(source.get("type", "file")),
                url=str(source.get("url", "")),
                realtime=bool(source.get("realtime", True)),
                loop=bool(source.get("loop", False)),
                device=source.get("device"),
                chunk_ms=int(source.get("chunk_ms", 100)),
            ),
            source_language=payload.get("source_language"),
            target_language=str(payload.get("target_language", "es")),
            video=str(payload.get("video", "")),
        )

    async def shutdown(self) -> None:
        for session in list(self.sessions.values()):
            await session.stop()
        self.sessions.clear()
        if self._engine is not None:
            await self._engine.aclose()
