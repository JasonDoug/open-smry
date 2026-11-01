"""
Summary AI — FastAPI Application Entrypoint (OpenAPI 3.1.0).
"""
from contextlib import asynccontextmanager
import re
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


class NormalizeSlashMiddleware:
    """
    BUG-001 Fix: Pure ASGI middleware that collapses consecutive slashes in request paths
    (e.g., //api/v1/health -> /api/v1/health) before Starlette/FastAPI route matching.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "")
            if "//" in path:
                normalized = re.sub(r"/+", "/", path)
                scope["path"] = normalized
                if "raw_path" in scope:
                    scope["raw_path"] = normalized.encode("utf-8")
        await self.app(scope, receive, send)

from app.api.v1.router import router as v1_router
from app.api.v1.extraction_router import extraction_router
from app.api.v1.library_router import library_router
from app.api.v1.agents_router import agents_router
from app.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    default_server_url = f"http://localhost:{settings.port}"
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Open-source agentic AI reading, summarizing, and research platform patterned after smry.ai. "
            "Powered by FastAPI, LangGraph multi-agent orchestration, Hybrid Vector/BM25 RAG with exact passage offsets, "
            "Edge-TTS neural Karaoke audio, and FastMCP."
        ),
        servers=[
            {
                "url": default_server_url,
                "description": "Local Summary AI Server (no trailing slash for Bruno/Postman import)",
            }
        ],
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        lifespan=lifespan,
    )
    application.openapi_version = "3.1.0"

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(NormalizeSlashMiddleware)

    application.include_router(v1_router)
    application.include_router(extraction_router)
    application.include_router(library_router)
    application.include_router(agents_router)

    @application.get("/", tags=["Root"], summary="Summary AI API Root & Sprint Status")
    def root_index() -> Dict[str, Any]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "sprint": "Sprint 4 — LangGraph Multi-Agent Orchestrator (Claude, GPT, Gemini, OpenRouter, Ollama), Verifiable Citation Critic & Streaming Chat",
            "no_account_required": True,
            "links": {
                "openapi_spec": "/openapi.json",
                "swagger_docs": "/docs",
                "redoc": "/redoc",
                "health": "/api/v1/health",
                "meta": "/api/v1/meta",
                "ai_providers": "/api/v1/models/providers",
                "extract_url": "/api/v1/extract/url",
                "extract_youtube": "/api/v1/extract/youtube",
                "extract_book": "/api/v1/extract/book",
                "library": "/api/v1/library",
                "library_hybrid_search": "/api/v1/library/search",
                "library_reindex": "/api/v1/library/reindex",
                "reading_history": "/api/v1/history",
                "cloud_sync_export": "/api/v1/sync/export",
                "summarize": "/api/v1/summarize",
                "ask_document": "/api/v1/documents/{document_id}/ask",
                "ask_context": "/api/v1/ask-context",
                "chat": "/api/v1/chat",
            },
        }

    return application


app = create_app()
