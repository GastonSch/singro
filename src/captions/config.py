from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "sessions.yaml"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class SourceConfig:
    type: str = "file"
    url: str = ""
    realtime: bool = True
    loop: bool = False
    device: int | None = None
    chunk_ms: int = 100


@dataclass
class SessionConfig:
    id: str
    name: str
    source: SourceConfig
    source_language: str | None = None
    target_language: str = "es"
    video: str = ""


@dataclass
class Settings:
    api_key: str = ""
    engine: str = "gemini_live"
    model: str = "gemini-3.5-live-translate-preview"
    rest_model: str = "gemini-3.8-flash"
    chunk_seconds: float = 4.0
    overlap_seconds: float = 0.5
    max_inflight: int = 4
    latency_target_ms: int = 2500
    flush_seconds: float = 6.0
    idle_seconds: float = 1.2
    native_translation: bool = True
    autostart: bool = False
    vad_silence_ms: int = 500
    thinking_level: str = ""
    glossary: dict[str, str] = field(default_factory=dict)
    sessions: list[SessionConfig] = field(default_factory=list)


def _source(raw: dict[str, Any]) -> SourceConfig:
    return SourceConfig(
        type=str(raw.get("type", "file")),
        url=str(raw.get("url", "")),
        realtime=bool(raw.get("realtime", True)),
        loop=bool(raw.get("loop", False)),
        device=raw.get("device"),
        chunk_ms=int(raw.get("chunk_ms", 100)),
    )


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path else DEFAULT_CONFIG
    data: dict[str, Any] = {}
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    elif path:
        raise FileNotFoundError(f"No existe la configuración: {config_path}")

    settings = Settings(
        api_key=os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""),
        engine=(os.getenv("CAPTIONS_ENGINE") or data.get("engine", "gemini_live")).lower(),
        model=os.getenv("CAPTIONS_MODEL") or data.get("model", "gemini-3.5-live-translate-preview"),
        rest_model=os.getenv("CAPTIONS_REST_MODEL") or data.get("rest_model", "gemini-3.8-flash"),
        chunk_seconds=float(data.get("chunk_seconds", 4.0)),
        overlap_seconds=float(data.get("overlap_seconds", 0.5)),
        max_inflight=int(data.get("max_inflight", 4)),
        latency_target_ms=int(data.get("latency_target_ms", 2500)),
        flush_seconds=float(data.get("flush_seconds", 6.0)),
        idle_seconds=float(data.get("idle_seconds", 1.2)),
        vad_silence_ms=int(data.get("vad_silence_ms", 500)),
        thinking_level=str(data.get("thinking_level", os.getenv("CAPTIONS_THINKING", ""))),
        native_translation=str(os.getenv("CAPTIONS_NATIVE_TRANSLATION", "")).lower()
        in {"1", "true", "yes"}
        or bool(data.get("native_translation", True)),
        autostart=str(os.getenv("CAPTIONS_AUTOSTART", "")).lower() in {"1", "true", "yes"}
        or bool(data.get("autostart", False)),
        glossary={str(k): str(v) for k, v in (data.get("glossary") or {}).items()},
    )

    for index, raw in enumerate(data.get("sessions") or []):
        session_id = str(raw.get("id", f"session-{index + 1}"))
        settings.sessions.append(
            SessionConfig(
                id=session_id,
                name=str(raw.get("name", session_id)),
                source=_source(raw.get("source") or {}),
                source_language=raw.get("source_language"),
                target_language=str(raw.get("target_language", "es")),
                video=str(raw.get("video", "")),
            )
        )
    return settings
