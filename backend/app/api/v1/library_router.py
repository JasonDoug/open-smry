"""
Sprint 3 FastAPI Router:
- Saved Library Management & Filtering (GET/PATCH/DELETE /api/v1/library)
- Hybrid BM25 + Dense Vector Search with Exact Offset Verification (POST /api/v1/library/search)
- Library Embedding Re-Indexer supporting Deterministic & Local Ollama Embeddings (POST /api/v1/library/reindex)
- Reading History Log (GET/DELETE /api/v1/history)
- Cross-Device Cloud Sync Export & Import (GET /api/v1/sync/export, POST /api/v1/sync/import)
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Document, PassageChunk, ReaderSession, ReadingHistory
from app.db.session import get_db
from app.rag.embeddings import compute_deterministic_embedding, compute_ollama_embedding
from app.rag.retriever import hybrid_search_passages
from app.schemas.domain import (
    CloudSyncImportRequest,
    CloudSyncSnapshotResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    LibraryItemSummarySchema,
    LibraryListResponse,
    LibraryUpdateRequest,
    ReaderSettingsSchema,
    ReadingHistoryItemSchema,
    ReadingHistoryResponse,
    ReindexLibraryRequest,
    ReindexLibraryResponse,
    RetrievedPassageSchema,
)

library_router = APIRouter(
    prefix="/api/v1",
    tags=["Sprint 3: Hybrid RAG Search, Exact Passage Verification, Library & Cloud Sync"],
)


def _doc_to_library_summary(doc: Document) -> LibraryItemSummarySchema:
    try:
        tags_list = json.loads(doc.tags_json or "[]")
    except Exception:
        tags_list = []

    return LibraryItemSummarySchema(
        id=doc.id,
        url=doc.url,
        title=doc.title,
        author=doc.author,
        site_name=doc.site_name,
        media_type=doc.media_type,
        excerpt=doc.excerpt,
        word_count=doc.word_count,
        reading_time_minutes=doc.reading_time_minutes,
        source_used=doc.source_used,
        saved_in_library=doc.saved_in_library,
        tags=tags_list,
        passage_count=len(doc.passages),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@library_router.get(
    "/library",
    response_model=LibraryListResponse,
    summary="List & Filter Saved Library Articles, Websites, YouTube Transcripts, and Books",
)
def list_library_documents(
    q: Optional[str] = Query(default=None, description="Optional keyword filter on title, excerpt, or URL"),
    tag: Optional[str] = Query(default=None, description="Optional tag filter (e.g., 'book', 'youtube', 'web')"),
    media_type: Optional[str] = Query(default=None, description="Optional media_type filter ('article', 'book', 'youtube')"),
    saved_only: bool = Query(default=True, description="Filter to documents marked saved_in_library=True"),
    db: Session = Depends(get_db),
) -> LibraryListResponse:
    stmt = select(Document).order_by(Document.created_at.desc())
    docs = list(db.scalars(stmt).all())

    filtered: List[LibraryItemSummarySchema] = []
    for doc in docs:
        if saved_only and not doc.saved_in_library:
            continue
        if media_type and doc.media_type.lower() != media_type.lower():
            continue
        summary = _doc_to_library_summary(doc)
        if tag and tag.lower() not in [t.lower() for t in summary.tags]:
            continue
        if q:
            q_lower = q.lower()
            haystack = f"{doc.title} {doc.excerpt or ''} {doc.url} {doc.author or ''}".lower()
            if q_lower not in haystack:
                continue
        filtered.append(summary)

    return LibraryListResponse(total=len(filtered), items=filtered)


@library_router.patch(
    "/library/{document_id}",
    response_model=LibraryItemSummarySchema,
    summary="Update a Library Document's Title, Tags, or Saved Status",
)
def update_library_document(
    document_id: str,
    payload: LibraryUpdateRequest,
    db: Session = Depends(get_db),
) -> LibraryItemSummarySchema:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    if payload.title is not None:
        doc.title = payload.title
    if payload.saved_in_library is not None:
        doc.saved_in_library = payload.saved_in_library
    if payload.tags is not None:
        unique_tags = list(dict.fromkeys(payload.tags))
        doc.tags_json = json.dumps(unique_tags)

    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _doc_to_library_summary(doc)


@library_router.delete(
    "/library/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Document and its Indexed Passages from the Library",
)
def delete_library_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )
    title = doc.title
    db.delete(doc)
    db.commit()
    return {
        "deleted": True,
        "document_id": document_id,
        "title": title,
    }


@library_router.post(
    "/library/search",
    response_model=HybridSearchResponse,
    summary="Hybrid BM25 + Dense Vector Search Returning Verifiable Exact-Offset Passages",
)
def search_library_passages(
    payload: HybridSearchRequest,
    db: Session = Depends(get_db),
) -> HybridSearchResponse:
    ranked, total_candidates = hybrid_search_passages(
        db,
        payload.query,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
        tag_filter=payload.tag,
        media_type_filter=payload.media_type,
        saved_only=payload.saved_only,
    )

    passages_out = [RetrievedPassageSchema(**item) for item in ranked]
    all_verified = all(p.offset_verified for p in passages_out)

    return HybridSearchResponse(
        query=payload.query,
        total_candidates_scanned=total_candidates,
        returned_count=len(passages_out),
        all_offsets_verified=all_verified,
        passages=passages_out,
    )


@library_router.post(
    "/library/reindex",
    response_model=ReindexLibraryResponse,
    summary="Recompute Passage Embeddings Across Library (Deterministic or Local Ollama /api/embed)",
    description=(
        "Recomputes and persists passage embeddings. When provider='ollama', high-dimensional vectors are stored in "
        "PassageChunk.embedding_json. Note that hybrid search currently relies on 256-dimensional deterministic embeddings "
        "for zero-latency ranking and falls back when query and stored dimensions differ; Ollama reindexing does not affect "
        "search ranking until query-time Ollama embedding matches the stored dimension."
    ),
)
async def reindex_library_embeddings(
    payload: ReindexLibraryRequest,
    db: Session = Depends(get_db),
) -> ReindexLibraryResponse:
    """
    Recomputes and stores passage embeddings across library documents.
    Note: Stored Ollama embeddings are persisted for downstream agentic use. Hybrid search falls back to
    deterministic embeddings if stored vector dimensions differ from the query embedding.
    """
    settings = get_settings()
    stmt = select(Document)
    docs = list(db.scalars(stmt).all())
    if payload.document_ids:
        docs = [d for d in docs if d.id in payload.document_ids]

    chunks_to_index: List[PassageChunk] = []
    for doc in docs:
        chunks_to_index.extend(doc.passages)

    if not chunks_to_index:
        return ReindexLibraryResponse(
            provider_used=payload.provider,
            documents_indexed=len(docs),
            passages_indexed=0,
            embedding_dimension=0,
        )

    provider_used = payload.provider
    dim = 256

    if payload.provider == "ollama":
        ollama_succeeded = True
        for chunk in chunks_to_index:
            vec = await compute_ollama_embedding(
                chunk.text,
                model=payload.ollama_model,
                base_url=settings.ollama_base_url,
            )
            if vec is None:
                ollama_succeeded = False
                vec = compute_deterministic_embedding(chunk.text)
            dim = len(vec)
            chunk.embedding_json = json.dumps(vec)
            db.add(chunk)
        if not ollama_succeeded:
            provider_used = "deterministic (fallback)"
    else:
        for chunk in chunks_to_index:
            vec = compute_deterministic_embedding(chunk.text)
            dim = len(vec)
            chunk.embedding_json = json.dumps(vec)
            db.add(chunk)

    db.commit()
    return ReindexLibraryResponse(
        provider_used=provider_used,
        documents_indexed=len(docs),
        passages_indexed=len(chunks_to_index),
        embedding_dimension=dim,
    )


@library_router.get(
    "/history",
    response_model=ReadingHistoryResponse,
    summary="List Recent Reading History Across Articles, Websites, YouTube Videos, and Books",
)
def get_reading_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ReadingHistoryResponse:
    stmt = select(ReadingHistory).order_by(ReadingHistory.accessed_at.desc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    items = [
        ReadingHistoryItemSchema(
            id=r.id,
            document_id=r.document_id,
            title=r.title,
            url=r.url,
            source_used=r.source_used,
            word_count=r.word_count,
            last_read_at=r.accessed_at,
        )
        for r in rows
    ]
    return ReadingHistoryResponse(total=len(items), items=items)


@library_router.delete(
    "/history",
    status_code=status.HTTP_200_OK,
    summary="Clear Reading History Log",
)
def clear_reading_history(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    stmt = select(ReadingHistory)
    rows = list(db.scalars(stmt).all())
    deleted_count = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return {"cleared": True, "deleted_count": deleted_count}


@library_router.get(
    "/sync/export",
    response_model=CloudSyncSnapshotResponse,
    summary="Export Cross-Device Cloud Sync Snapshot (Reader Settings, Saved Library & History)",
)
def export_cloud_sync_snapshot(
    session_id: str = Query(default="demo-session", description="Anonymous or synced session ID"),
    db: Session = Depends(get_db),
) -> CloudSyncSnapshotResponse:
    session_row = db.get(ReaderSession, session_id)
    if session_row:
        reader_settings = ReaderSettingsSchema(
            theme=session_row.theme,  # type: ignore[arg-type]
            font_id=session_row.font_id,
            font_size_px=session_row.font_size_px,
            line_height=session_row.line_height,
            margin_width=session_row.margin_width,  # type: ignore[arg-type]
            preferred_provider=session_row.preferred_provider,  # type: ignore[arg-type]
            preferred_model=session_row.preferred_model,
            preferred_voice_id=session_row.preferred_voice_id,
            preferred_tts_speed=session_row.preferred_tts_speed,
        )
    else:
        reader_settings = ReaderSettingsSchema()

    docs = list(db.scalars(select(Document).order_by(Document.created_at.desc())).all())
    saved_items = [_doc_to_library_summary(d) for d in docs if d.saved_in_library]

    hist_rows = list(db.scalars(select(ReadingHistory).order_by(ReadingHistory.accessed_at.desc()).limit(100)).all())
    history_items = [
        ReadingHistoryItemSchema(
            id=r.id,
            document_id=r.document_id,
            title=r.title,
            url=r.url,
            source_used=r.source_used,
            word_count=r.word_count,
            last_read_at=r.accessed_at,
        )
        for r in hist_rows
    ]

    return CloudSyncSnapshotResponse(
        session_id=session_id,
        settings=reader_settings,
        library_count=len(saved_items),
        history_count=len(history_items),
        library_items=saved_items,
        reading_history=history_items,
        exported_at=datetime.now(timezone.utc),
    )


@library_router.post(
    "/sync/import",
    response_model=CloudSyncSnapshotResponse,
    summary="Import & Reconcile Cross-Device Cloud Sync Snapshot",
)
def import_cloud_sync_snapshot(
    payload: CloudSyncImportRequest,
    db: Session = Depends(get_db),
) -> CloudSyncSnapshotResponse:
    session_row = db.get(ReaderSession, payload.session_id)
    if not session_row:
        session_row = ReaderSession(id=payload.session_id, is_anonymous=False)
        db.add(session_row)

    if payload.settings is not None:
        session_row.theme = payload.settings.theme
        session_row.font_id = payload.settings.font_id
        session_row.font_size_px = payload.settings.font_size_px
        session_row.line_height = payload.settings.line_height
        session_row.margin_width = payload.settings.margin_width
        session_row.preferred_provider = payload.settings.preferred_provider
        session_row.preferred_model = payload.settings.preferred_model
        session_row.preferred_voice_id = payload.settings.preferred_voice_id
        session_row.preferred_tts_speed = payload.settings.preferred_tts_speed
        db.add(session_row)

    for doc_id in payload.saved_document_ids:
        doc = db.get(Document, doc_id)
        if doc:
            doc.saved_in_library = True
            db.add(doc)

    db.commit()
    return export_cloud_sync_snapshot(session_id=payload.session_id, db=db)
