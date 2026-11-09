"""
Sprint 7 FastAPI Router:
- List the 10 Neural TTS Voices (GET /api/v1/tts/voices)
- Synthesize Neural Speech with Karaoke Word-Boundary Timings
  (POST /api/v1/tts/synthesize) — returns base64 audio + exact character-offset
  word timings; offline fallback guarantees the reader never hard-fails.
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import TTS_VOICES
from app.tts.engine import synthesize_speech, validate_voice_id

logger = logging.getLogger(__name__)

tts_router = APIRouter(
    prefix="/api/v1/tts",
    tags=["Sprint 7: Neural TTS & Karaoke Word Sync"],
)

MAX_TEXT_CHARS = 10_000


class TTSVoicesResponse(BaseModel):
    """Catalog of the 10 neural voices with gender/accent metadata."""

    voices: List[Dict[str, Any]]


class TTSSynthesizeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Paste or load an article, then listen with karaoke word sync.",
                "voice_id": "aria-us-f",
                "speed": 1.0,
            }
        }
    )
    text: str = Field(
        min_length=1,
        max_length=MAX_TEXT_CHARS,
        description="Text to narrate (article body, transcript, or selection)",
    )
    voice_id: str = Field(default="aria-us-f", description="One of the 10 platform voices")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Playback rate 0.5x–2.0x")


class KaraokeWordSchema(BaseModel):
    """Exact word timing anchored to source character offsets."""

    word_index: int
    start_ms: int
    end_ms: int
    char_start: int
    char_end: int
    text: str


class TTSSynthesizeResponse(BaseModel):
    """Audio payload (base64) plus karaoke word timings aligned to the source text."""

    voice_id: str
    speed: float
    mime_type: str
    synthesis_engine: str
    audio_base64: str
    duration_ms: int
    words: List[KaraokeWordSchema] = Field(default_factory=list)


@tts_router.get(
    "/voices",
    response_model=TTSVoicesResponse,
    summary="List the 10 Neural TTS Voices & Accents (US, UK, AU, IN, IE/EU, CA)",
)
def list_tts_voices() -> TTSVoicesResponse:
    """Returns the platform's neural voice catalog with edge-tts mappings."""
    return TTSVoicesResponse(voices=TTS_VOICES)


@tts_router.post(
    "/synthesize",
    response_model=TTSSynthesizeResponse,
    summary="Synthesize Neural Speech with Karaoke Word-Boundary Timings ([start_ms,end_ms,char_start,char_end])",
)
async def synthesize(payload: TTSSynthesizeRequest) -> TTSSynthesizeResponse:
    """
    Narrates the supplied text and returns base64 audio plus word timings whose
    character offsets satisfy text[char_start:char_end] == word for karaoke sync.
    """
    try:
        validate_voice_id(payload.voice_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    try:
        result = await synthesize_speech(
            payload.text,
            payload.voice_id,
            payload.speed,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surfaced as 502 for observability
        logger.exception("TTS synthesis failed unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Speech synthesis failed: {exc}",
        ) from exc

    return TTSSynthesizeResponse(
        voice_id=result.voice_id,
        speed=result.speed,
        mime_type=result.mime_type,
        synthesis_engine=result.synthesis_engine,
        audio_base64=base64.b64encode(result.audio).decode("ascii"),
        duration_ms=result.duration_ms,
        words=[KaraokeWordSchema(**w.as_dict()) for w in result.words],
    )
