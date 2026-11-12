"""
Sprint 2 FastAPI Router:
- Multi-Source URL Extraction & Soft-Paywall Mirror Racing (POST /api/v1/extract/url)
- YouTube Video Transcript Extraction (POST /api/v1/extract/youtube)
- Book & Long-Form Document Ingestion: PDF, EPUB, Markdown/Text (POST /api/v1/extract/book)
- Document Retrieval with Exact-Offset Passages (GET /api/v1/documents/{document_id})
- One-Click Copy to LLMs Clean Markdown Utility (GET /api/v1/documents/{document_id}/copy-to-llm)
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.db.models import Document, PassageChunk, ReadingHistory
from app.db.session import get_db
from app.extraction.books import (
    parse_epub_bytes,
    parse_pdf_bytes,
    parse_text_or_markdown_book,
)
from app.extraction.racer import extract_from_url
from app.extraction.youtube import extract_youtube_transcript
from app.rag.embeddings import compute_deterministic_embedding
from app.schemas.domain import (
    CopyToLlmResponse,
    ExtractBookRequest,
    ExtractedDocumentResponse,
    ExtractUrlRequest,
    ExtractYouTubeRequest,
    PassageChunkSchema,
    SourceAttemptSchema,
    TranscriptSegmentSchema,
)

extraction_router = APIRouter(
    prefix="/api/v1",
    tags=["Sprint 2: Multi-Source Extraction, YouTube Transcripts & Books"],
)


def get_http_client() -> Optional[httpx.AsyncClient]:
    """Dependency hook allowing test suites to inject a mock httpx.AsyncClient."""
    return None


def _persist_extracted_document(
    db: Session,
    extracted: Dict[str, Any],
    *,
    save_to_library: bool = True,
    tags: Optional[List[str]] = None,
    title_override: Optional[str] = None,
) -> ExtractedDocumentResponse:
    final_title = title_override or extracted.get("title") or "Untitled Document"
    source_attempts = extracted.get("source_attempts") or []
    tag_list = list(dict.fromkeys(tags or []))

    doc = Document(
        url=extracted.get("url") or "local://document",
        canonical_url=extracted.get("canonical_url"),
        image_url=extracted.get("image_url"),
        title=final_title,
        author=extracted.get("author"),
        site_name=extracted.get("site_name"),
        published_time=extracted.get("published_time"),
        media_type=extracted.get("media_type") or "article",
        excerpt=extracted.get("excerpt"),
        content_html=extracted.get("content_html") or "",
        text_content=extracted.get("text_content") or "",
        llm_markdown=extracted.get("llm_markdown") or "",
        word_count=int(extracted.get("word_count", 0)),
        reading_time_minutes=int(extracted.get("reading_time_minutes", 1)),
        stripped_elements_count=int(extracted.get("stripped_elements_count", 0)),
        source_used=extracted.get("source_used") or "direct",
        source_score=float(extracted.get("source_score", 0.0)),
        source_attempts_json=json.dumps(source_attempts),
        saved_in_library=save_to_library,
        paywall_detected=bool(extracted.get("paywall_detected")),
        tags_json=json.dumps(tag_list),
    )
    db.add(doc)
    db.flush()

    for p in extracted.get("passages") or []:
        passage_text = str(p["text"])
        embedding_vec = compute_deterministic_embedding(passage_text)
        chunk = PassageChunk(
            document_id=doc.id,
            paragraph_index=int(p["paragraph_index"]),
            chapter_title=p.get("chapter_title"),
            page_or_timestamp=p.get("page_or_timestamp"),
            start_char=int(p["start_char"]),
            end_char=int(p["end_char"]),
            text=passage_text,
            embedding_json=json.dumps(embedding_vec),
        )
        db.add(chunk)

    hist = ReadingHistory(
        document_id=doc.id,
        title=doc.title,
        url=doc.url,
        source_used=doc.source_used,
        word_count=doc.word_count,
    )
    db.add(hist)
    db.commit()
    db.refresh(doc)

    return _document_to_response(
        doc,
        transcript_segments=extracted.get("transcript_segments"),
    )


def _document_to_response(
    doc: Document,
    transcript_segments: Optional[List[Dict[str, Any]]] = None,
) -> ExtractedDocumentResponse:
    """Serializes a Document ORM row (and optional transcript segments) into the API response model."""
    try:
        attempts_raw = json.loads(doc.source_attempts_json or "[]")
    except Exception:
        attempts_raw = []

    try:
        tags_raw = json.loads(doc.tags_json or "[]")
    except Exception:
        tags_raw = []

    return ExtractedDocumentResponse(
        id=doc.id,
        url=doc.url,
        canonical_url=doc.canonical_url,
        image_url=doc.image_url,
        title=doc.title,
        author=doc.author,
        site_name=doc.site_name,
        published_time=doc.published_time,
        media_type=doc.media_type,
        excerpt=doc.excerpt,
        content_html=doc.content_html,
        text_content=doc.text_content,
        llm_markdown=doc.llm_markdown,
        word_count=doc.word_count,
        reading_time_minutes=doc.reading_time_minutes,
        stripped_elements_count=doc.stripped_elements_count,
        source_used=doc.source_used,
        source_score=doc.source_score,
        source_attempts=[SourceAttemptSchema(**a) for a in attempts_raw],
        saved_in_library=doc.saved_in_library,
        paywall_detected=bool(doc.paywall_detected),
        tags=tags_raw,
        passages=[
            PassageChunkSchema(
                id=p.id,
                paragraph_index=p.paragraph_index,
                chapter_title=p.chapter_title,
                page_or_timestamp=p.page_or_timestamp,
                start_char=p.start_char,
                end_char=p.end_char,
                text=p.text,
            )
            for p in doc.passages
        ],
        transcript_segments=(
            [TranscriptSegmentSchema(**s) for s in transcript_segments]
            if transcript_segments is not None
            else None
        ),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@extraction_router.post(
    "/extract/url",
    response_model=ExtractedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Extract Distraction-Free Article or Website by Racing Mirrors (Direct, Wayback, Cache, Jina)",
)
async def extract_article_url(
    payload: ExtractUrlRequest,
    db: Session = Depends(get_db),
    http_client: Optional[httpx.AsyncClient] = Depends(get_http_client),
) -> ExtractedDocumentResponse:
    try:
        extracted = await extract_from_url(
            payload.url,
            preferred_source=payload.source,
            raw_html_override=payload.raw_html,
            http_client=http_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Extraction failed for %s", payload.url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {exc}",
        ) from exc

    return _persist_extracted_document(
        db,
        extracted,
        save_to_library=payload.save_to_library,
        tags=payload.tags,
        title_override=payload.title_override,
    )


@extraction_router.post(
    "/extract/youtube",
    response_model=ExtractedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Extract Timestamped Readable Transcript from a YouTube Video Link",
)
async def extract_youtube_video(
    payload: ExtractYouTubeRequest,
    db: Session = Depends(get_db),
    http_client: Optional[httpx.AsyncClient] = Depends(get_http_client),
) -> ExtractedDocumentResponse:
    try:
        extracted = await extract_youtube_transcript(
            payload.url,
            languages=payload.languages,
            http_client=http_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return _persist_extracted_document(
        db,
        extracted,
        save_to_library=payload.save_to_library,
        tags=payload.tags,
    )


@extraction_router.post(
    "/extract/book",
    response_model=ExtractedDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest & Parse a Book or Long-Form Document (PDF, EPUB, Markdown, or Plain Text)",
)
def extract_book_document(
    payload: ExtractBookRequest,
    db: Session = Depends(get_db),
) -> ExtractedDocumentResponse:
    fmt = payload.format.lower()
    try:
        if fmt == "pdf":
            if not payload.file_base64:
                raise ValueError("file_base64 is required when format='pdf'.")
            pdf_bytes = base64.b64decode(payload.file_base64)
            extracted = parse_pdf_bytes(
                pdf_bytes,
                title_override=payload.title,
                author_override=payload.author,
                source_url=payload.source_url,
            )
        elif fmt == "epub":
            if not payload.file_base64:
                raise ValueError("file_base64 is required when format='epub'.")
            epub_bytes = base64.b64decode(payload.file_base64)
            extracted = parse_epub_bytes(
                epub_bytes,
                title_override=payload.title,
                author_override=payload.author,
                source_url=payload.source_url,
            )
        else:
            if not payload.text_content or not payload.text_content.strip():
                raise ValueError("text_content is required when format is 'markdown' or 'text'.")
            extracted = parse_text_or_markdown_book(
                payload.text_content,
                title=payload.title,
                author=payload.author,
                source_url=payload.source_url,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse {fmt} book: {exc}",
        ) from exc

    return _persist_extracted_document(
        db,
        extracted,
        save_to_library=payload.save_to_library,
        tags=payload.tags,
    )


@extraction_router.get(
    "/documents/{document_id}",
    response_model=ExtractedDocumentResponse,
    summary="Get an Extracted Article, Book, Website, or YouTube Transcript with Exact Passage Offsets",
)
def get_extracted_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> ExtractedDocumentResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )
    return _document_to_response(doc)


@extraction_router.get(
    "/documents/{document_id}/copy-to-llm",
    response_model=CopyToLlmResponse,
    summary="One-Click Export of Stripped Article/Book into Clean Markdown Ready for ChatGPT, Claude, or Local LLMs",
)
def get_document_copy_to_llm(
    document_id: str,
    db: Session = Depends(get_db),
) -> CopyToLlmResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )
    return CopyToLlmResponse(
        document_id=doc.id,
        title=doc.title,
        url=doc.url,
        source_used=doc.source_used,
        word_count=doc.word_count,
        llm_markdown=doc.llm_markdown,
    )
