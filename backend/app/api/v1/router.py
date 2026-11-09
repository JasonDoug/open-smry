"""
Sprint 1 Core API v1 Router:
- System Health & Database Status (/api/v1/health)
- Platform Metadata & Constants (/api/v1/meta)
- No-Account-Required Anonymous Sessions & Reader Customization (/api/v1/sessions/...)
- Multi-Provider AI Discovery: Claude, GPT, Gemini, OpenRouter & Local Ollama (/api/v1/models/providers)
"""
import secrets
from typing import Any, Dict, List
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import ReaderSession
from app.db.session import get_db
from app.schemas.domain import (
    AI_MODELS,
    AI_PROVIDERS,
    EXTRACTION_SOURCES,
    HIGHLIGHT_COLORS,
    READER_FONTS,
    SUMMARY_MODES,
    TTS_VOICES,
    AnonymousSessionResponse,
    PlatformMetaResponse,
    ReaderSettingsSchema,
    ReaderSettingsUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["Sprint 1: Foundation, Meta & Sessions"])

VALID_FONT_IDS = {f["id"] for f in READER_FONTS}
VALID_VOICE_IDS = {v["id"] for v in TTS_VOICES}


def _session_to_response(sess: ReaderSession) -> AnonymousSessionResponse:
    return AnonymousSessionResponse(
        session_id=sess.id,
        is_anonymous=sess.is_anonymous,
        no_account_required=True,
        sync_token=sess.sync_token,
        settings=ReaderSettingsSchema(
            theme=sess.theme,  # type: ignore[arg-type]
            font_id=sess.font_id,
            font_size_px=sess.font_size_px,
            line_height=sess.line_height,
            margin_width=sess.margin_width,  # type: ignore[arg-type]
            preferred_provider=sess.preferred_provider,  # type: ignore[arg-type]
            preferred_model=sess.preferred_model,
            preferred_voice_id=sess.preferred_voice_id,
            preferred_tts_speed=sess.preferred_tts_speed,
        ),
        created_at=sess.created_at,
        updated_at=sess.updated_at,
    )


@router.get("/health", summary="Check API, Database & AI Provider Readiness")
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": "connected",
        "no_account_required": True,
        "providers_configured": {
            "claude": bool(settings.anthropic_api_key),
            "gpt": bool(settings.openai_api_key),
            "gemini": bool(settings.gemini_api_key),
            "openrouter": bool(settings.openrouter_api_key),
            "ollama_base_url": settings.ollama_base_url,
            "local_openai_base_url": settings.local_openai_base_url,
        },
    }


@router.get(
    "/meta",
    response_model=PlatformMetaResponse,
    summary="Get 7 Reader Fonts (incl. OpenDyslexic), 5 Highlight Colors, 10 TTS Voices & 5 AI Provider Families",
)
def get_platform_meta() -> PlatformMetaResponse:
    return PlatformMetaResponse(
        reader_fonts=READER_FONTS,
        highlight_colors=HIGHLIGHT_COLORS,
        extraction_sources=EXTRACTION_SOURCES,
        summary_modes=SUMMARY_MODES,
        ai_providers=AI_PROVIDERS,
        ai_models=AI_MODELS,
        tts_voices=TTS_VOICES,
        default_reader_settings=ReaderSettingsSchema(),
    )


@router.post(
    "/sessions/anonymous",
    response_model=AnonymousSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a No-Account-Required Instant Reader Session",
)
def create_anonymous_session(
    initial_settings: ReaderSettingsUpdateRequest | None = None,
    db: Session = Depends(get_db),
) -> AnonymousSessionResponse:
    sess = ReaderSession(
        is_anonymous=True,
        sync_token=f"sync_{secrets.token_urlsafe(16)}",
    )
    if initial_settings:
        updates = initial_settings.model_dump(exclude_unset=True)
        if "font_id" in updates and updates["font_id"] not in VALID_FONT_IDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid font_id '{updates['font_id']}'. Must be one of: {sorted(VALID_FONT_IDS)}",
            )
        for key, value in updates.items():
            if value is not None:
                setattr(sess, key, value)

    db.add(sess)
    db.commit()
    db.refresh(sess)
    return _session_to_response(sess)


@router.get(
    "/sessions/{session_id}",
    response_model=AnonymousSessionResponse,
    summary="Retrieve Reader Session & Typography Preferences",
)
def get_reader_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> AnonymousSessionResponse:
    sess = db.get(ReaderSession, session_id)
    if not sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found")
    return _session_to_response(sess)


@router.patch(
    "/sessions/{session_id}/settings",
    response_model=AnonymousSessionResponse,
    summary="Update Reader Customization (Theme, 7 Fonts incl. OpenDyslexic, Size, Spacing, Margins, AI & TTS)",
)
def update_reader_session_settings(
    session_id: str,
    payload: ReaderSettingsUpdateRequest,
    db: Session = Depends(get_db),
) -> AnonymousSessionResponse:
    sess = db.get(ReaderSession, session_id)
    if not sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found")

    updates = payload.model_dump(exclude_unset=True)
    if "font_id" in updates and updates["font_id"] not in VALID_FONT_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid font_id '{updates['font_id']}'. Must be one of: {sorted(VALID_FONT_IDS)}",
        )
    if "preferred_voice_id" in updates and updates["preferred_voice_id"] not in VALID_VOICE_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid preferred_voice_id '{updates['preferred_voice_id']}'. Must be one of: {sorted(VALID_VOICE_IDS)}",
        )

    for field, val in updates.items():
        if val is not None:
            setattr(sess, field, val)

    db.commit()
    db.refresh(sess)
    return _session_to_response(sess)


@router.get(
    "/models/providers",
    summary="Discover Cloud LLMs (Claude, GPT, Gemini), OpenRouter & Local AI (Ollama / LM Studio / vLLM)",
)
async def discover_ai_providers(
    probe_ollama: bool = True,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    ollama_models: List[str] = []
    ollama_reachable = False

    if probe_ollama:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                if resp.status_code == 200:
                    ollama_reachable = True
                    data = resp.json()
                    ollama_models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception:
            ollama_reachable = False

    return {
        "providers": AI_PROVIDERS,
        "preset_models": AI_MODELS,
        "openrouter": {
            "base_url": settings.openrouter_base_url,
            "api_key_configured": bool(settings.openrouter_api_key),
            "default_model": settings.openrouter_default_model,
            "free_router": settings.openrouter_free_router,
            "supports_custom_model_id": True,
        },
        "local_ai": {
            "ollama_base_url": settings.ollama_base_url,
            "ollama_reachable": ollama_reachable,
            "ollama_default_model": settings.ollama_default_model,
            "ollama_embedding_model": settings.ollama_embedding_model,
            "discovered_ollama_models": ollama_models,
            "local_openai_base_url": settings.local_openai_base_url,
        },
    }
