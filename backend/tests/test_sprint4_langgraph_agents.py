"""
Sprint 4 Test Suite:
- Multi-LLM Router & LangGraph Multi-Agent Architecture
- 5-Mode AI Summaries (tldr, bullets, takeaways, executive, custom)
- Map-Reduce Summarization for long documents (>15 passages)
- Verifiable Exact-Passage Q&A + Citation Verifier Critic Loop
- Contextual "Ask AI" Excerpt Analyst
- Conversational Chat with SSE text/event-stream Streaming & Thread Persistence
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path):
    """Isolated per-test database so test runs never pollute the live .data DB."""
    from app.db.session import get_db, get_engine, get_session_factory, init_db

    engine = get_engine(f"sqlite:///{tmp_path / 'test_sprint4.db'}")
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


def test_summarize_modes_and_persistence(client) -> None:
    # 1. Ingest test article
    ingest_res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Agentic Verification Architecture",
            "author": "Dr. Claude Shannon",
            "format": "markdown",
            "text_content": (
                "# Chapter 1: The Principle of Verifiable Extraction\n\n"
                "Unverified generative synthesis frequently produces hallucinations. "
                "Grounding every summary sentence in exact-offset quotations eliminates citation fraud.\n\n"
                "# Chapter 2: Multi-Mirror Resilience\n\n"
                "Racing multiple web mirrors concurrently guarantees high availability against soft paywalls and rate limits."
            ),
            "save_to_library": True,
            "tags": ["sprint4", "agentic-ai"],
        },
    )
    assert ingest_res.status_code == 201
    doc_id = ingest_res.json()["id"]

    # 2. Test 'tldr' mode
    tldr_res = client.post(
        "/api/v1/summarize",
        json={"document_id": doc_id, "mode": "tldr"},
    )
    assert tldr_res.status_code == 201
    tldr_data = tldr_res.json()
    assert tldr_data["mode"] == "tldr"
    assert len(tldr_data["content"]) > 10
    assert tldr_data["word_count"] > 0
    assert tldr_data["reading_time_saved_minutes"] >= 1

    # 3. Test 'bullets' mode
    bullets_res = client.post(
        "/api/v1/summarize",
        json={"document_id": doc_id, "mode": "bullets"},
    )
    assert bullets_res.status_code == 201
    bullets_data = bullets_res.json()
    assert bullets_data["mode"] == "bullets"
    assert len(bullets_data["key_points"]) > 0

    # 4. Test 'takeaways' mode
    takeaways_res = client.post(
        "/api/v1/summarize",
        json={"document_id": doc_id, "mode": "takeaways"},
    )
    assert takeaways_res.status_code == 201
    assert takeaways_res.json()["mode"] == "takeaways"

    # 5. Test 'executive' mode
    exec_res = client.post(
        "/api/v1/summarize",
        json={"document_id": doc_id, "mode": "executive"},
    )
    assert exec_res.status_code == 201
    assert exec_res.json()["mode"] == "executive"

    # 6. Test 'custom' prompt mode
    custom_res = client.post(
        "/api/v1/summarize",
        json={
            "document_id": doc_id,
            "mode": "custom",
            "custom_prompt": "Explain the significance of exact offsets for legal discovery in 2 paragraphs.",
        },
    )
    assert custom_res.status_code == 201
    assert custom_res.json()["mode"] == "custom"

    # 7. Check persistence in GET /api/v1/documents/{document_id}/summaries
    list_res = client.get(f"/api/v1/documents/{doc_id}/summaries")
    assert list_res.status_code == 200
    summaries = list_res.json()
    assert len(summaries) >= 5
    assert any(s["mode"] == "tldr" for s in summaries)
    assert any(s["mode"] == "executive" for s in summaries)

    # 8. Test validation: custom mode without custom_prompt must return 422
    invalid_custom = client.post(
        "/api/v1/summarize",
        json={"document_id": doc_id, "mode": "custom", "custom_prompt": ""},
    )
    assert invalid_custom.status_code == 422
    assert "custom_prompt is required" in invalid_custom.text


def test_map_reduce_long_document(client) -> None:
    # Generate 18 distinct paragraphs to trigger Map-Reduce
    paragraphs = [
        f"Paragraph {i}: Detailed analytical passage examining system component number {i} with distinct technical specifications and empirical measurements."
        for i in range(1, 19)
    ]
    long_text = "\n\n".join(paragraphs)

    ingest_res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Comprehensive Engineering Handbook",
            "author": "Systems Working Group",
            "format": "text",
            "text_content": long_text,
            "save_to_library": True,
            "tags": ["map-reduce-test"],
        },
    )
    assert ingest_res.status_code == 201
    doc_id = ingest_res.json()["id"]
    assert len(ingest_res.json()["passages"]) == 18

    # Summarize via Map-Reduce
    sum_res = client.post(
        "/api/v1/summarize",
        json={"document_id": doc_id, "mode": "executive"},
    )
    assert sum_res.status_code == 201
    data = sum_res.json()
    assert data["mode"] == "executive"
    assert len(data["content"]) > 50


def test_verifiable_qa_with_critic_agent(client) -> None:
    ingest_res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Scientific Foundations of Smry",
            "format": "markdown",
            "text_content": (
                "# Section A\n\n"
                "The primary mechanism of Smry is verifiable citation checking, "
                "anchoring every claim to exact character coordinates.\n\n"
                "# Section B\n\n"
                "Reciprocal Rank Fusion ensures that neither pure keyword matching "
                "nor pure semantic search dominates retrieval."
            ),
            "save_to_library": True,
            "tags": ["verifiable-qa"],
        },
    )
    assert ingest_res.status_code == 201
    doc_data = ingest_res.json()
    doc_id = doc_data["id"]
    full_text = doc_data["text_content"]

    # Ask document with critic verification
    ask_res = client.post(
        f"/api/v1/documents/{doc_id}/ask",
        json={
            "document_id": doc_id,
            "question": "What does Reciprocal Rank Fusion do in the system?",
            "top_k": 3,
        },
    )
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert ask_data["document_id"] == doc_id
    assert len(ask_data["answer"]) > 10
    assert len(ask_data["citations"]) > 0
    assert ask_data["all_citations_verified"] is True

    # Check that citations match full_text exactly
    top_citation = ask_data["citations"][0]
    assert top_citation["offset_verified"] is True
    assert (
        full_text[top_citation["start_char"] : top_citation["end_char"]]
        == top_citation["exact_quote"]
    )

    # Missing question must fail validation with 422
    bad_ask = client.post(f"/api/v1/documents/{doc_id}/ask", json={"document_id": doc_id})
    assert bad_ask.status_code == 422


def test_contextual_excerpt_analyst(client) -> None:
    quote = "Grounding every summary sentence in exact-offset quotations eliminates citation fraud."
    ingest_res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Context Analyst Target Document",
            "format": "text",
            "text_content": f"Introduction.\n\n{quote}\n\nConclusion.",
            "save_to_library": True,
        },
    )
    assert ingest_res.status_code == 201
    doc_data = ingest_res.json()
    doc_id = doc_data["id"]
    full_text = doc_data["text_content"]
    start_c = full_text.index(quote)
    end_c = start_c + len(quote)

    # Test "explain"
    explain_res = client.post(
        "/api/v1/ask-context",
        json={
            "document_id": doc_id,
            "selected_text": quote,
            "start_char": start_c,
            "end_char": end_c,
            "action_or_question": "explain",
        },
    )
    assert explain_res.status_code == 200
    explain_data = explain_res.json()
    assert explain_data["offset_verified"] is True
    assert len(explain_data["analysis"]) > 10

    # Test "critique"
    critique_res = client.post(
        "/api/v1/ask-context",
        json={
            "document_id": doc_id,
            "selected_text": quote,
            "start_char": start_c,
            "end_char": end_c,
            "action_or_question": "critique",
        },
    )
    assert critique_res.status_code == 200
    assert critique_res.json()["offset_verified"] is True

    # Missing selected_text must fail validation with 422
    bad_ctx = client.post("/api/v1/ask-context", json={"document_id": doc_id})
    assert bad_ctx.status_code == 422


def test_chat_interaction_and_sse_streaming(client) -> None:
    # 1. Standard JSON chat
    chat_res = client.post(
        "/api/v1/chat",
        json={
            "message": "Hello research assistant, what are the core capabilities of Summary AI?",
        },
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    thread_id = chat_data["thread_id"]
    assert chat_data["role"] == "assistant"
    assert len(chat_data["content"]) > 10

    # 2. Streaming chat with ?stream=true (SSE)
    stream_res = client.post(
        "/api/v1/chat?stream=true",
        json={
            "thread_id": thread_id,
            "message": "Explain how multi-source racing prevents soft paywalls.",
        },
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]
    stream_body = stream_res.text
    assert "data: " in stream_body
    assert "data: [DONE]" in stream_body

    # 3. Retrieve thread history
    thread_res = client.get(f"/api/v1/chat/{thread_id}")
    assert thread_res.status_code == 200
    thread_data = thread_res.json()
    assert thread_data["id"] == thread_id
    assert len(thread_data["messages"]) >= 4  # 2 user messages + 2 assistant messages

    # 4. Delete thread
    del_res = client.delete(f"/api/v1/chat/{thread_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 5. Confirm 404 after delete
    get_deleted = client.get(f"/api/v1/chat/{thread_id}")
    assert get_deleted.status_code == 404

    # 6. Validation & Error Handling:
    # Missing message must return 422
    bad_msg = client.post("/api/v1/chat", json={})
    assert bad_msg.status_code == 422

    # Non-existent thread_id must return 404
    bad_thread = client.post(
        "/api/v1/chat",
        json={"thread_id": "non_existent_thread_xyz", "message": "hello"},
    )
    assert bad_thread.status_code == 404

    # Non-existent document_id on thread creation must return 404
    bad_doc = client.post(
        "/api/v1/chat",
        json={"document_id": "non_existent_doc_xyz", "message": "hello"},
    )
    assert bad_doc.status_code == 404


def test_persisted_keys_require_strong_session_credential():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from fastapi import HTTPException
    from app.api.v1.agents_router import _resolve_api_keys
    from app.db.models import ReaderSession

    db = Mock()
    db.get.return_value = SimpleNamespace(
        anthropic_api_key="saved", openai_api_key=None,
        gemini_api_key=None, openrouter_api_key=None,
    )
    with pytest.raises(HTTPException) as exc:
        _resolve_api_keys(db, "sess_0123456789ab", None)
    assert exc.value.status_code == 403
    db.get.assert_not_called()
    assert _resolve_api_keys(db, "sess_0123456789ab", {"openai": "override"}) == {"openai": "override"}
    db.get.assert_not_called()
    assert _resolve_api_keys(db, None, None) == {}
    credential = "sess_" + "a" * 48
    assert _resolve_api_keys(db, credential, {"anthropic": "override"}) == {"anthropic": "override"}
    db.get.assert_called_with(ReaderSession, credential)
    assert _resolve_api_keys(db, credential, None) == {"anthropic": "saved"}
    db.get.return_value = None
    assert _resolve_api_keys(db, credential, None) == {}


def test_stream_resolves_keys_before_response(client, monkeypatch):
    from app.api.v1 import agents_router as module

    def reject(*args):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid credential")

    monkeypatch.setattr(module, "_resolve_api_keys", reject)
    response = client.post("/api/v1/chat?stream=true", json={"message": "Hello"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid credential"
