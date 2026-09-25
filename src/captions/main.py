from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import PROJECT_ROOT, Settings, load_settings
from .events import EventBus
from .manager import SessionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("captions")

STATIC_DIR = Path(__file__).parent / "static"
SAMPLES_DIR = PROJECT_ROOT / "samples"
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4", ".webm", ".aac"}
settings: Settings = load_settings(os.getenv("CAPTIONS_CONFIG"))
bus = EventBus()
manager = SessionManager(settings, bus)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await manager.load_configured()
    except Exception as exc:
        log.error("No se pudieron iniciar las sesiones configuradas: %s", exc)
    yield
    await manager.shutdown()


app = FastAPI(title="Sincro", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/overlay")
async def overlay() -> FileResponse:
    return FileResponse(STATIC_DIR / "overlay.html")


@app.get("/monitor")
async def monitor() -> FileResponse:
    return FileResponse(STATIC_DIR / "monitor.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "engine": settings.engine,
        "model": settings.model,
        "api_key_configured": bool(settings.api_key),
        "sessions": len(manager.sessions),
    }


@app.get("/api/sessions")
async def list_sessions() -> list[dict]:
    return manager.list()


@app.get("/api/samples")
async def list_samples() -> list[str]:
    if not SAMPLES_DIR.exists():
        return []
    return sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in SAMPLES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
    )


@app.post("/api/sessions", status_code=201)
async def create_session(payload: dict = Body(...)) -> dict:
    if "id" not in payload:
        raise HTTPException(status_code=400, detail="Falta el campo 'id'")
    try:
        config = manager.from_payload(payload)
        session = await manager.add(config)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return session.snapshot()


@app.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    try:
        await manager.remove(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada") from exc


@app.post("/api/sessions/{session_id}/start")
async def start_session(session_id: str) -> dict:
    try:
        await manager.start(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada") from exc
    return manager.sessions[session_id].snapshot()


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str) -> dict:
    try:
        await manager.stop(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada") from exc
    return manager.sessions[session_id].snapshot()


def _format_time(seconds: float, vtt: bool = False) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def _render_transcript(session, fmt: str, lang: str) -> str:  # noqa: ANN001
    started = session.stats.get("started_at") or 0.0
    blocks = session.blocks

    def text_for(block: dict) -> str:
        original = block.get("original", "")
        translation = block.get("translation", "")
        if lang == "original":
            return original
        if lang == "both" and original and translation and original != translation:
            return f"{original}\n{translation}"
        return translation or original

    if fmt == "json":
        import json

        return json.dumps(
            [{"ts": block["ts"], "original": block["original"], "translation": block["translation"]} for block in blocks],
            ensure_ascii=False,
            indent=2,
        )

    if fmt == "txt":
        return "\n".join(text_for(block) for block in blocks if text_for(block)) + "\n"

    lines: list[str] = []
    if fmt == "vtt":
        lines.append("WEBVTT")
        lines.append("")
    for index, block in enumerate(blocks, start=1):
        text = text_for(block)
        if not text:
            continue
        start = block["ts"] - started
        end = blocks[index]["ts"] - started if index < len(blocks) else start + 4.0
        if end <= start:
            end = start + 2.0
        if fmt == "srt":
            lines.append(str(index))
            lines.append(f"{_format_time(start)} --> {_format_time(end)}")
            lines.append(text)
            lines.append("")
        else:
            lines.append(f"{_format_time(start, vtt=True)} --> {_format_time(end, vtt=True)}")
            lines.append(text)
            lines.append("")
    return "\n".join(lines) + "\n"


@app.get("/api/sessions/{session_id}/transcript")
async def transcript(
    session_id: str,
    format: str = Query("srt", pattern="^(srt|vtt|txt|json)$"),
    lang: str = Query("translation", pattern="^(translation|original|both)$"),
) -> PlainTextResponse:
    session = manager.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    body = _render_transcript(session, format, lang)
    media_type = "application/json" if format == "json" else "text/plain; charset=utf-8"
    headers = {"Content-Disposition": f'attachment; filename="{session_id}.{format}"'}
    return PlainTextResponse(body, media_type=media_type, headers=headers)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await bus.subscribe()
    await websocket.send_json({"type": "sessions", "sessions": manager.list()})

    async def sender() -> None:
        while True:
            event = await queue.get()
            await websocket.send_json(event)

    async def receiver() -> None:
        while True:
            await websocket.receive_text()

    sender_task = asyncio.create_task(sender())
    receiver_task = asyncio.create_task(receiver())
    try:
        done, pending = await asyncio.wait(
            {sender_task, receiver_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await bus.unsubscribe(queue)
        for task in (sender_task, receiver_task):
            task.cancel()
