"""
Natural Voice Neural TTS Engine with Karaoke Word-Boundary Alignment.

Primary synthesis uses `edge-tts` neural voices (10 male/female profiles across
US/UK/AU/IN/IE/CA accents) streaming MP3 audio with native WordBoundary events.
When edge-tts or the network is unavailable, a deterministic offline fallback
synthesizes a WAV file with proportional per-word timings so the Karaoke
experience keeps working with zero external dependencies.
"""
from __future__ import annotations

import asyncio
import io
import math
import re
import struct
import wave
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.schemas.domain import TTS_VOICES

_VALID_VOICE_IDS = {v["id"] for v in TTS_VOICES}


class TTSError(Exception):
    """Raised when speech synthesis fails for a non-recoverable reason."""


def validate_voice_id(voice_id: str) -> str:
    """Ensures the requested voice id exists in the 10-voice platform catalog."""
    voice_id = (voice_id or "").strip()
    if voice_id not in _VALID_VOICE_IDS:
        raise ValueError(
            f"Unknown voice_id '{voice_id}'. Must be one of: {sorted(_VALID_VOICE_IDS)}"
        )
    return voice_id


def _edge_voice_for(voice_id: str) -> str:
    """Maps a platform voice id (e.g. 'aria-us-f') to its edge-tts voice name."""
    for voice in TTS_VOICES:
        if voice["id"] == voice_id:
            return voice["edge_voice"]
    raise TTSError(f"No edge voice mapping for '{voice_id}'")


@dataclass
class KaraokeWord:
    """A single word boundary aligned to exact character offsets in the source text."""

    word_index: int
    start_ms: int
    end_ms: int
    char_start: int
    char_end: int
    text: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "word_index": self.word_index,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "text": self.text,
        }


@dataclass
class TTSResult:
    """Synthesized audio plus karaoke word-boundary timings."""

    audio: bytes
    mime_type: str
    voice_id: str
    speed: float
    words: List[KaraokeWord] = field(default_factory=list)
    synthesis_engine: str = "edge-tts"

    @property
    def duration_ms(self) -> int:
        """Total narrated duration in milliseconds (0 when no words were timed)."""
        return self.words[-1].end_ms if self.words else 0


def _tokenize_words(text: str) -> List[Dict[str, Any]]:
    """Splits text into words while preserving exact character offsets.

    Offsets are computed on the *unmodified* input text so that
    text[char_start:char_end] == word holds for every entry.
    """
    tokens: List[Dict[str, Any]] = []
    for match in re.finditer(r"\S+", text or ""):
        tokens.append(
            {
                "text": match.group(0),
                "char_start": match.start(),
                "char_end": match.end(),
            }
        )
    return tokens


def align_word_boundaries(
    text: str,
    boundaries: List[Dict[str, Any]],
) -> List[KaraokeWord]:
    """
    Aligns raw TTS word-boundary events to exact character offsets in `text`.

    Boundary events provide spoken word text plus timing; because TTS engines do
    not report source character offsets, each event is matched to the next
    unaligned word token in the source text (case/punctuation tolerant) so the
    returned timings satisfy text[char_start:char_end] coverage in reading order.
    Events that cannot be matched (e.g. engine tokenization quirks) are skipped.
    """
    tokens = _tokenize_words(text)
    karaoke: List[KaraokeWord] = []
    token_idx = 0
    for idx, b in enumerate(boundaries):
        spoken = str(b.get("text", "")).strip()
        if not spoken or token_idx >= len(tokens):
            continue
        # Advance past any tokens the engine merged/split until a tolerant match.
        matched = None
        while token_idx < len(tokens):
            candidate = tokens[token_idx]["text"]
            if candidate.lower().strip(".,;:!?\"'()[]{}") == spoken.lower().strip(".,;:!?\"'()[]{}"):
                matched = tokens[token_idx]
                break
            # Tolerate engine splitting hyphenated/contracted words: accept prefix match.
            if len(spoken) >= 3 and candidate.lower().startswith(spoken.lower()[:3]):
                matched = tokens[token_idx]
                break
            token_idx += 1
        if matched is None:
            continue
        token_idx += 1
        start_ms = max(0, int(round(b.get("start_ms", 0))))
        end_ms = max(start_ms, int(round(b.get("end_ms", 0))))
        karaoke.append(
            KaraokeWord(
                word_index=len(karaoke),
                start_ms=start_ms,
                end_ms=end_ms,
                char_start=matched["char_start"],
                char_end=matched["char_end"],
                text=matched["text"],
            )
        )
    # Renumber sequentially for a stable UI index.
    for order, word in enumerate(karaoke):
        word.word_index = order
    return karaoke


# ---------------------------------------------------------------------------
# Offline deterministic fallback synthesis
# ---------------------------------------------------------------------------

_SAMPLE_RATE = 8000
_MS_PER_CHAR_BASE = 55.0


def _fallback_word_timings(text: str, speed: float) -> List[KaraokeWord]:
    """Produces proportional word timings (chars -> milliseconds) for fallback audio."""
    tokens = _tokenize_words(text)
    if not tokens:
        return []
    factor = _MS_PER_CHAR_BASE / max(0.25, speed)
    words: List[KaraokeWord] = []
    cursor_ms = 250  # small lead-in so the first word is not clipped
    for order, token in enumerate(tokens):
        # Longer words are spoken longer; punctuation pauses after the word.
        core = token["text"].strip(".,;:!?\"'()[]{}")
        char_ms = factor * max(1, len(core))
        pause = factor * 3 if token["text"].endswith((".", "!", "?")) else factor * 1.5
        start_ms = int(cursor_ms)
        end_ms = int(cursor_ms + char_ms)
        words.append(
            KaraokeWord(
                word_index=order,
                start_ms=start_ms,
                end_ms=end_ms,
                char_start=token["char_start"],
                char_end=token["char_end"],
                text=token["text"],
            )
        )
        cursor_ms = end_ms + pause
    return words


def _fallback_synthesize(text: str, speed: float) -> bytes:
    """
    Renders an offline WAV: each word is a short tone burst whose duration matches
    its karaoke timing, separated by silence. Pure stdlib (wave/struct/math).
    """
    words = _fallback_word_timings(text, speed)
    total_ms = words[-1].end_ms + 400 if words else 400
    total_samples = int(_SAMPLE_RATE * total_ms / 1000)
    samples = [0.0] * total_samples

    for word in words:
        start_sample = int(_SAMPLE_RATE * word.start_ms / 1000)
        end_sample = min(total_samples, int(_SAMPLE_RATE * word.end_ms / 1000))
        span = max(1, end_sample - start_sample)
        freq = 220.0 + (word.word_index % 5) * 40.0  # gentle pitch variation
        for i in range(span):
            t = i / _SAMPLE_RATE
            envelope = math.sin(math.pi * i / span)  # attack/decay per word
            samples[start_sample + i] = 0.35 * envelope * math.sin(2 * math.pi * freq * t)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE)
        frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
        wav.writeframes(frames)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# edge-tts primary synthesis
# ---------------------------------------------------------------------------


async def _edge_synthesize(text: str, voice_id: str, speed: float) -> TTSResult:
    """Synthesizes neural MP3 audio with native WordBoundary events via edge-tts."""
    try:
        import edge_tts
    except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
        raise TTSError(f"edge-tts is not installed: {exc}") from exc

    edge_voice = _edge_voice_for(voice_id)
    rate_pct = int(round((speed - 1.0) * 100))  # +25% => "+25%"
    # edge-tts 7.x defaults to sentence boundaries; karaoke needs word-level events.
    communicate = edge_tts.Communicate(
        text, edge_voice, rate=f"{rate_pct:+d}%", boundary="WordBoundary"
    )

    audio = bytearray()
    boundaries: List[Dict[str, Any]] = []
    async for event in communicate.stream():
        if event["type"] == "audio":
            audio.extend(event["data"])
        elif event["type"] == "WordBoundary":
            # edge-tts reports 100-nanosecond units.
            start_ms = event["offset"] / 10_000.0
            duration_ms = event["duration"] / 10_000.0
            boundaries.append(
                {
                    "text": event.get("text", ""),
                    "start_ms": start_ms,
                    "end_ms": start_ms + duration_ms,
                }
            )

    if not audio:
        raise TTSError("edge-tts produced no audio data")

    return TTSResult(
        audio=bytes(audio),
        mime_type="audio/mpeg",
        voice_id=voice_id,
        speed=speed,
        words=align_word_boundaries(text, boundaries),
        synthesis_engine="edge-tts",
    )


async def synthesize_speech(
    text: str,
    voice_id: str = "aria-us-f",
    speed: float = 1.0,
    *,
    force_fallback: bool = False,
) -> TTSResult:
    """
    Synthesizes neural speech with karaoke word timings.

    Tries edge-tts first; on any failure (offline, network error, empty audio)
    falls back to the deterministic offline WAV synthesizer so the reader's
    Karaoke experience never hard-fails.
    """
    validate_voice_id(voice_id)
    if not text or not text.strip():
        raise ValueError("text must contain speakable content")
    if not 0.5 <= speed <= 2.0:
        raise ValueError("speed must be between 0.5 and 2.0")

    if not force_fallback:
        try:
            result = await _edge_synthesize(text, voice_id, speed)
            if not result.words:
                # Engine returned audio but no boundary events (older/newer
                # versions, API drift). Graft proportional timings so karaoke
                # still tracks the audio approximately.
                result.words = _fallback_word_timings(text, speed)
            return result
        except Exception as exc:  # noqa: BLE001 - fallback must catch everything
            # Surface the reason in logs but keep the karaoke path alive.
            import logging

            logging.getLogger(__name__).warning(
                "edge-tts synthesis failed (%s); using offline fallback", exc
            )

    words = _fallback_word_timings(text, speed)
    return TTSResult(
        audio=_fallback_synthesize(text, speed),
        mime_type="audio/wav",
        voice_id=voice_id,
        speed=speed,
        words=words,
        synthesis_engine="offline-fallback",
    )
