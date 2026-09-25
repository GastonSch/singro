import asyncio
import io
import wave

from captions.audio import FFmpegAudioSource, MicrophoneAudioSource, build_source, pcm_to_wav
from captions.config import Settings, SourceConfig, load_settings
from captions.engines.mock import MockEngine
from captions.events import EventBus
from captions.main import _render_transcript


def _audio_chunks(count: int):
    async def generator():
        for _ in range(count):
            yield b"\x00\x00" * 1600  # 100 ms of 16 kHz mono s16le

    return generator()


def test_pcm_to_wav_is_valid():
    data = pcm_to_wav(b"\x01\x00" * 16000)
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getnframes() == 16000


def test_build_source_types():
    assert isinstance(build_source(SourceConfig(type="file", url="x.mp3")), FFmpegAudioSource)
    assert isinstance(build_source(SourceConfig(type="mic")), MicrophoneAudioSource)


def test_event_bus_pubsub():
    async def scenario():
        bus = EventBus()
        queue = await bus.subscribe()
        bus.publish({"type": "caption", "text": "hola"})
        assert (await queue.get())["text"] == "hola"
        await bus.unsubscribe(queue)
        bus.publish({"type": "caption", "text": "nadie"})
        assert queue.empty()

    asyncio.run(scenario())


def test_mock_engine_emits_blocks():
    async def scenario():
        events = []

        async def emit(event):
            events.append(event)

        await MockEngine(Settings()).run(
            _audio_chunks(60), emit, session_id="t", source_language="en", target_language="es"
        )
        return events

    events = asyncio.run(scenario())
    assert len(events) >= 2
    assert all(event.kind == "block" for event in events)
    assert events[0].original and events[0].translation


def test_load_settings(tmp_path, monkeypatch):
    for name in ("CAPTIONS_ENGINE", "CAPTIONS_MODEL", "CAPTIONS_REST_MODEL"):
        monkeypatch.delenv(name, raising=False)
    config = tmp_path / "s.yaml"
    config.write_text(
        "engine: mock\nsessions:\n  - id: a\n    name: A\n    source: {type: file, url: x.mp3}\n"
    )
    settings = load_settings(config)
    assert settings.engine == "mock"
    assert len(settings.sessions) == 1
    assert settings.sessions[0].id == "a"


def _fake_session(blocks):
    class Fake:
        stats = {"started_at": 100.0}
        pass

    session = Fake()
    session.blocks = blocks
    return session


def test_render_transcript_formats():
    session = _fake_session(
        [
            {"ts": 102.0, "original": "Hello world", "translation": "Hola mundo"},
            {"ts": 105.5, "original": "Second line", "translation": "Segunda línea"},
        ]
    )
    srt = _render_transcript(session, "srt", "translation")
    assert "00:00:02,000 --> 00:00:05,500" in srt
    assert "Hola mundo" in srt

    vtt = _render_transcript(session, "vtt", "translation")
    assert vtt.startswith("WEBVTT")
    assert "00:00:02.000 --> 00:00:05.500" in vtt

    txt = _render_transcript(session, "txt", "both")
    assert "Hello world" in txt and "Hola mundo" in txt

    json_text = _render_transcript(session, "json", "translation")
    assert '"translation": "Hola mundo"' in json_text
