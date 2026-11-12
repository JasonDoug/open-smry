"""
Sprint 3 Test Suite:
- Hybrid BM25 + Dense Vector Cosine Similarity + RRF Search (/api/v1/library/search)
- Exact Character-Offset Invariant Verification (doc.text_content[start_char:end_char] == exact_quote)
- Saved Library CRUD & Tag/Media-Type Filtering (/api/v1/library)
- Library Embedding Re-Indexer (/api/v1/library/reindex)
- Reading History Log (/api/v1/history)
- Cross-Device Cloud Sync Snapshot Export & Import (/api/v1/sync/export, /api/v1/sync/import)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.retriever import verify_exact_offset_invariant


@pytest.fixture()
def client(tmp_path):
    """Isolated per-test database so test runs never pollute the live .data DB."""
    from app.db.session import get_db, get_engine, get_session_factory, init_db

    engine = get_engine(f"sqlite:///{tmp_path / 'test_sprint3.db'}")
    init_db(engine)
    TestingSessionLocal = get_session_factory(engine)

    test_app = app

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as test_client:
        yield test_client
    test_app.dependency_overrides.pop(get_db, None)


def test_exact_offset_invariant_unit() -> None:
    full_text = "Paragraph one about neural search.\n\nParagraph two about exact character offsets."
    quote = "Paragraph two about exact character offsets."
    start_idx = full_text.index(quote)
    end_idx = start_idx + len(quote)

    assert verify_exact_offset_invariant(full_text, start_idx, end_idx, quote) is True
    # Tampered offset must fail verification
    assert verify_exact_offset_invariant(full_text, start_idx + 1, end_idx, quote) is False
    assert verify_exact_offset_invariant(full_text, -1, end_idx, quote) is False

    # Test Document and PassageChunk objects without fallback search
    from app.db.models import Document, PassageChunk
    doc = Document(id="doc_test", text_content=full_text)
    valid_chunk = PassageChunk(id="c1", document_id="doc_test", start_char=start_idx, end_char=end_idx, text=quote)
    verified, val = verify_exact_offset_invariant(doc, valid_chunk)
    assert verified is True
    assert val == quote

    # Tampered chunk offsets must strictly fail and not fall back to finding quote elsewhere
    tampered_chunk = PassageChunk(id="c2", document_id="doc_test", start_char=0, end_char=10, text=quote)
    verified_bad, _ = verify_exact_offset_invariant(doc, tampered_chunk)
    assert verified_bad is False


def test_hybrid_rag_search_and_exact_offset_verification(client) -> None:
    book_payload = {
        "title": "Architecture of Verifiable RAG Systems",
        "author": "Dr. Grace Hopper",
        "format": "markdown",
        "text_content": (
            "# Chapter 1: Lexical BM25 Retrieval\n\n"
            "BM25Okapi excels at exact lexical keyword matching for rare technical identifiers and error codes.\n\n"
            "# Chapter 2: Dense Semantic Vector Embeddings\n\n"
            "Dense vector cosine similarity captures conceptual paraphrases and semantic relationships across passages.\n\n"
            "# Chapter 3: Reciprocal Rank Fusion and Offset Verification\n\n"
            "Combining BM25 and dense vectors with Reciprocal Rank Fusion while verifying start_char and end_char eliminates hallucinated citations."
        ),
        "save_to_library": True,
        "tags": ["rag", "architecture", "sprint3-test"],
    }
    ingest_res = client.post("/api/v1/extract/book", json=book_payload)
    assert ingest_res.status_code == 201
    doc_data = ingest_res.json()
    doc_id = doc_data["id"]
    full_text = doc_data["text_content"]

    # Run Hybrid BM25 + Vector search scoped to this document
    search_res = client.post(
        "/api/v1/library/search",
        json={
            "query": "Reciprocal Rank Fusion start_char and end_char eliminates hallucinated citations",
            "top_k": 3,
            "document_ids": [doc_id],
        },
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    # total_candidates_scanned must reflect the 3 filtered candidate passages, not global DB count
    assert search_data["total_candidates_scanned"] == 3
    assert search_data["returned_count"] == 3
    assert search_data["all_offsets_verified"] is True

    # Search with non-matching document ID must report 0 candidates scanned
    empty_res = client.post(
        "/api/v1/library/search",
        json={
            "query": "Reciprocal Rank Fusion",
            "top_k": 3,
            "document_ids": ["non_existent_doc_id"],
        },
    )
    assert empty_res.status_code == 200
    assert empty_res.json()["total_candidates_scanned"] == 0
    assert empty_res.json()["returned_count"] == 0

    top_passage = search_data["passages"][0]
    assert top_passage["document_id"] == doc_id
    assert top_passage["offset_verified"] is True
    assert "Reciprocal Rank Fusion" in top_passage["exact_quote"]
    assert top_passage["hybrid_score"] > 0
    # Verify exact slice against document text_content
    assert full_text[top_passage["start_char"] : top_passage["end_char"]] == top_passage["exact_quote"]


def test_library_crud_and_filtering(client) -> None:
    res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Library Filter Target Document",
            "author": "Alan Turing",
            "format": "text",
            "text_content": "First passage about universal computation.\n\nSecond passage about decidability.",
            "save_to_library": True,
            "tags": ["computation", "unique-tag-xyz"],
        },
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Filter library by tag
    list_res = client.get("/api/v1/library", params={"tag": "unique-tag-xyz"})
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(item["id"] == doc_id for item in items)

    # Update title and tags via PATCH
    patch_res = client.patch(
        f"/api/v1/library/{doc_id}",
        json={
            "title": "Updated Turing Computation Monograph",
            "saved_in_library": True,
            "tags": ["computation", "updated-tag"],
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["title"] == "Updated Turing Computation Monograph"
    assert "updated-tag" in patched["tags"]

    # Delete from library
    del_res = client.delete(f"/api/v1/library/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Confirm 404 after delete
    get_res = client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 404

    # Reading history must not keep entries pointing at the deleted document
    hist_items = client.get("/api/v1/history?limit=100").json()["items"]
    assert all(item["document_id"] != doc_id for item in hist_items)


def test_library_reindex_and_reading_history_and_cloud_sync(client) -> None:
    res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Cloud Sync & Reindex Test Book",
            "format": "markdown",
            "text_content": "# Section A\n\nReindexing embeddings across all passages in the library.",
            "save_to_library": True,
            "tags": ["sync-test"],
        },
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Reindex deterministic embeddings for this document
    reindex_res = client.post(
        "/api/v1/library/reindex",
        json={
            "provider": "deterministic",
            "document_ids": [doc_id],
        },
    )
    assert reindex_res.status_code == 200
    r_data = reindex_res.json()
    assert r_data["documents_indexed"] == 1
    assert r_data["passages_indexed"] >= 1
    assert r_data["embedding_dimension"] == 256

    # Check reading history
    hist_res = client.get("/api/v1/history")
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] >= 1

    # Test Cloud Sync Import & Export
    sync_import = client.post(
        "/api/v1/sync/import",
        json={
            "session_id": "sprint3-sync-session",
            "settings": {
                "theme": "sepia",
                "font_id": "opendyslexic",
                "font_size_px": 22,
                "line_height": 1.9,
                "margin_width": "wide",
                "preferred_provider": "openrouter",
                "preferred_model": "openrouter/free",
                "preferred_voice_id": "aria-us-f",
                "preferred_tts_speed": 1.0,
            },
            "saved_document_ids": [doc_id],
        },
    )
    assert sync_import.status_code == 200
    snap = sync_import.json()
    assert snap["session_id"] == "sprint3-sync-session"
    assert snap["settings"]["font_id"] == "opendyslexic"
    assert snap["settings"]["preferred_model"] == "openrouter/free"
    assert snap["library_count"] >= 1
