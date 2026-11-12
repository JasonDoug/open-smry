"""
Sprint 7 Automated Test Suite:
- TTS voice catalog endpoint (10 voices/accents)
- Offline fallback synthesis (deterministic WAV, no network) via /api/v1/tts/synthesize
- Karaoke word-boundary invariant: text[char_start:char_end] == word, monotonic timings
- Word-click seek contract: timings must be usable to jump audio playback
- Validation: unknown voice 422, empty text 422, speed bounds 422
"""
from __future__ import annotations

import base64
import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tts import engine as tts_engine
from app.tts.engine import (
    TTSError,
    TTSResult,
    _fallback_word_timings,
    align_word_boundaries,
    synthesize_speech,
)


@pytest.fixture()
def client(tmp_path):
    """Isolated per-test database so test runs never pollute the live .data DB."""
    from app.db.session import get_db, get_engine, get_session_factory, init_db

    engine = get_engine(f"sqlite:///{tmp_path / 'test_sprint7.db'}")
    init_db(engine)
    TestingSessionLocal = get_session_factory(engine)

    def override_get_db():
        """Yields a session bound to the per-test SQLite database."""
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def test_tts_voices_catalog(client) -> None:
    """The catalog exposes all 10 voices across the six supported accents."""
    res = client.get("/api/v1/tts/voices")
    assert res.status_code == 200
    voices = res.json()["voices"]
    assert len(voices) == 10
    accents = {v["lang"] for v in voices}
    assert {"en-US", "en-GB", "en-AU", "en-IN", "en-IE", "en-CA"} <= accents
    assert all("edge_voice" in v for v in voices)


@pytest.mark.asyncio
async def test_fallback_synthesis_is_deterministic_wav() -> None:
    """Forced fallback yields a valid mono 16-bit PCM WAV without network access."""
    text = "Karaoke narration must keep working offline."
    result = await synthesize_speech(text, "aria-us-f", 1.0, force_fallback=True)
    assert result.synthesis_engine == "offline-fallback"
    assert result.mime_type == "audio/wav"
    assert len(result.audio) > 100

    # The audio must be a valid mono 16-bit PCM WAV.
    wav = wave.open(io.BytesIO(result.audio), "rb")
    assert wav.getnchannels() == 1
    assert wav.getsampwidth() == 2
    wav.close()


@pytest.mark.asyncio
async def test_karaoke_word_offsets_satisfy_exact_slice_invariant() -> None:
    """Every timed word slices back to itself and timings are monotonic."""
    text = (
        "Grounding every spoken word in exact character offsets keeps narration "
        "verifiable against the source document."
    )
    result = await synthesize_speech(text, "marcus-us-m", 1.0, force_fallback=True)
    assert result.words, "fallback must always produce word timings"
    for word in result.words:
        assert text[word.char_start : word.char_end] == word.text
    # Timings must be monotonic and non-overlapping in reading order.
    previous = None
    for word in result.words:
        assert word.start_ms <= word.end_ms
        if previous is not None:
            assert word.char_start > previous.char_start
            assert word.start_ms >= previous.end_ms
        previous = word


def test_align_word_boundaries_matches_engine_events() -> None:
    """Engine boundary events map onto exact source offsets, tolerating punctuation."""
    text = "Exact offsets anchor every citation."
    # Simulated edge-tts style events (already in ms).
    boundaries = [
        {"text": "Exact", "start_ms": 100, "end_ms": 300},
        {"text": "offsets", "start_ms": 300, "end_ms": 600},
        {"text": "anchor", "start_ms": 600, "end_ms": 900},
        {"text": "every", "start_ms": 900, "end_ms": 1100},
        {"text": "citation", "start_ms": 1100, "end_ms": 1500},
    ]
    karaoke = align_word_boundaries(text, boundaries)
    assert [w.text for w in karaoke] == ["Exact", "offsets", "anchor", "every", "citation."]
    assert text[karaoke[0].char_start : karaoke[0].char_end] == "Exact"
    assert karaoke[0].start_ms == 100
    assert karaoke[-1].end_ms == 1500


def test_fallback_timings_scale_with_speed() -> None:
    """Slower narration spreads proportional fallback timings further apart."""
    text = "Slow narration spreads word timings further apart than fast narration."
    slow = _fallback_word_timings(text, 0.5)
    fast = _fallback_word_timings(text, 2.0)
    assert slow[-1].end_ms > fast[-1].end_ms * 2


def test_align_word_boundaries_survives_unmatched_event() -> None:
    """An unmatched event mid-stream is skipped without dropping later words."""
    text = "Visit the U.S. today and then there"
    spoken = ["Visit", "the", "US", "today", "and", "then", "there"]
    boundaries = [
        {"text": w, "start_ms": i * 100, "end_ms": i * 100 + 90}
        for i, w in enumerate(spoken)
    ]
    karaoke = align_word_boundaries(text, boundaries)
    assert [w.text for w in karaoke] == ["Visit", "the", "today", "and", "then", "there"]
    for word in karaoke:
        assert text[word.char_start : word.char_end] == word.text
    # Later words keep their own engine timings (no shift from the skipped event).
    assert karaoke[2].start_ms == 300
    assert karaoke[-1].start_ms == 600


def _offline_edge(monkeypatch) -> None:
    """Makes edge-tts fail deterministically so the offline fallback is exercised."""

    async def _raise(*_args, **_kwargs):
        raise TTSError("edge-tts disabled in tests")

    monkeypatch.setattr(tts_engine, "_edge_synthesize", _raise)


def test_tts_synthesize_endpoint_offline_fallback(client, monkeypatch) -> None:
    """With edge-tts unavailable the endpoint serves the offline WAV fallback."""
    _offline_edge(monkeypatch)
    payload = {
        "text": "The reader highlights each word as the audio plays.",
        "voice_id": "elena-uk-f",
        "speed": 1.5,
    }
    res = client.post("/api/v1/tts/synthesize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["voice_id"] == "elena-uk-f"
    assert data["speed"] == 1.5
    assert data["synthesis_engine"] == "offline-fallback"
    assert data["mime_type"] == "audio/wav"
    audio = base64.b64decode(data["audio_base64"])
    assert len(audio) > 100
    words = data["words"]
    assert len(words) >= 8
    full_text = payload["text"]
    for w in words:
        assert full_text[w["char_start"] : w["char_end"]] == w["text"]
    # Word-click seek contract: every word exposes start_ms usable for currentTime seeks.
    assert all(w["start_ms"] >= 0 for w in words)


def test_tts_synthesize_endpoint_edge_path(client, monkeypatch) -> None:
    """A successful (stubbed) edge-tts result is returned as MP3 with its timings."""
    text = "Neural narration stays in sync."

    async def _fake_edge(text_arg, voice_id, speed):
        boundaries = [
            {"text": w, "start_ms": i * 200, "end_ms": i * 200 + 180}
            for i, w in enumerate(["Neural", "narration", "stays", "in", "sync"])
        ]
        return TTSResult(
            audio=b"ID3fake-mp3-bytes",
            mime_type="audio/mpeg",
            voice_id=voice_id,
            speed=speed,
            words=align_word_boundaries(text_arg, boundaries),
            synthesis_engine="edge-tts",
        )

    monkeypatch.setattr(tts_engine, "_edge_synthesize", _fake_edge)
    res = client.post(
        "/api/v1/tts/synthesize",
        json={"text": text, "voice_id": "aria-us-f", "speed": 1.0},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["synthesis_engine"] == "edge-tts"
    assert data["mime_type"] == "audio/mpeg"
    assert base64.b64decode(data["audio_base64"]) == b"ID3fake-mp3-bytes"
    assert [w["text"] for w in data["words"]] == ["Neural", "narration", "stays", "in", "sync."]
    assert data["duration_ms"] == 980


def test_tts_synthesize_validation_errors(client) -> None:
    """Unknown voices, out-of-range speeds, and empty text are rejected with 422."""
    bad_voice = client.post(
        "/api/v1/tts/synthesize",
        json={"text": "hello", "voice_id": "not-a-voice", "speed": 1.0},
    )
    assert bad_voice.status_code == 422
    assert "not-a-voice" in bad_voice.json()["detail"]

    bad_speed = client.post(
        "/api/v1/tts/synthesize",
        json={"text": "hello", "voice_id": "aria-us-f", "speed": 3.0},
    )
    assert bad_speed.status_code == 422

    empty_text = client.post(
        "/api/v1/tts/synthesize",
        json={"text": "", "voice_id": "aria-us-f", "speed": 1.0},
    )
    assert empty_text.status_code == 422
