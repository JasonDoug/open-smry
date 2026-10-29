"""
Sprint 1 Automated Test Suite:
Tests SQLAlchemy 2.0 ORM models, exact passage offset persistence,
FastAPI OpenAPI 3.1.0 specification, No-Account-Required anonymous sessions,
reader typography customization (7 fonts incl. OpenDyslexic), and
Multi-Provider AI discovery (Claude, GPT, Gemini, OpenRouter, Local Ollama).
"""
import hashlib
import pytest
from fastapi.testclient import TestClient

from app.db.models import (
    Annotation,
    ApiKey,
    ChatMessage,
    ChatThread,
    Document,
    PassageChunk,
    ReadingHistory,
    RssFeed,
    RssFeedItem,
    SummaryRecord,
)
from app.db.session import get_db, get_engine, get_session_factory, init_db
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "test_sprint1.db"
    engine = get_engine(f"sqlite:///{db_file}")
    init_db(engine)
    TestingSessionLocal = get_session_factory(engine)

    app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal


def test_openapi_3_1_and_health(client):
    test_client, _ = client
    openapi_res = test_client.get("/openapi.json")
    assert openapi_res.status_code == 200
    spec = openapi_res.json()
    assert spec["openapi"] == "3.1.0"
    assert "servers" in spec and len(spec["servers"]) >= 1
    assert not spec["servers"][0]["url"].endswith("/"), "BUG-002: server URL must not end with a trailing slash for Bruno OpenAPI import"
    assert "/api/v1/meta" in spec["paths"]
    assert "/api/v1/sessions/anonymous" in spec["paths"]
    assert "/api/v1/models/providers" in spec["paths"]

    health_res = test_client.get("/api/v1/health")
    assert health_res.status_code == 200
    health = health_res.json()
    assert health["status"] == "ok"
    assert health["database"] == "connected"
    assert health["no_account_required"] is True
    assert "openrouter" in health["providers_configured"]
    assert "ollama_base_url" in health["providers_configured"]


def test_double_slash_path_normalization_bug_001(client):
    """
    Regression test for BUG-001:
    Verify that duplicate slashes in URLs (e.g. http://localhost:8000//api/v1/health)
    are normalized and routed cleanly instead of returning 404.
    """
    test_client, _ = client
    res1 = test_client.get("http://testserver//api/v1/health")
    assert res1.status_code == 200
    assert res1.json()["status"] == "ok"

    res2 = test_client.get("http://testserver///api/v1//meta")
    assert res2.status_code == 200
    assert len(res2.json()["reader_fonts"]) == 7


def test_platform_meta_fonts_colors_voices_and_providers(client):
    test_client, _ = client
    res = test_client.get("/api/v1/meta")
    assert res.status_code == 200
    meta = res.json()

    # 7 Reader fonts including OpenDyslexic
    assert len(meta["reader_fonts"]) == 7
    font_ids = {f["id"] for f in meta["reader_fonts"]}
    assert "opendyslexic" in font_ids
    assert "atkinson" in font_ids

    # 5 Highlight colors
    assert len(meta["highlight_colors"]) == 5

    # 10 Neural TTS voices across accents
    assert len(meta["tts_voices"]) == 10

    # 5 AI Provider families including OpenRouter and Local Ollama
    provider_ids = {p["id"] for p in meta["ai_providers"]}
    assert provider_ids == {"claude", "gpt", "gemini", "openrouter", "ollama"}


def test_no_account_anonymous_session_and_reader_customization(client):
    test_client, _ = client

    # 1. Create instant anonymous session (No Account Required)
    create_res = test_client.post(
        "/api/v1/sessions/anonymous",
        json={"theme": "sepia", "font_id": "opendyslexic", "font_size_px": 22},
    )
    assert create_res.status_code == 201
    sess = create_res.json()
    session_id = sess["session_id"]
    assert sess["is_anonymous"] is True
    assert sess["no_account_required"] is True
    assert sess["sync_token"].startswith("sync_")
    assert sess["settings"]["theme"] == "sepia"
    assert sess["settings"]["font_id"] == "opendyslexic"
    assert sess["settings"]["font_size_px"] == 22

    # 2. Update session to use OpenRouter or Local Ollama + wide margins
    patch_res = test_client.patch(
        f"/api/v1/sessions/{session_id}/settings",
        json={
            "margin_width": "wide",
            "line_height": 2.0,
            "preferred_provider": "ollama",
            "preferred_model": "ollama/llama3.2",
            "preferred_voice_id": "elena-uk-f",
            "preferred_tts_speed": 1.5,
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["settings"]["margin_width"] == "wide"
    assert updated["settings"]["preferred_provider"] == "ollama"
    assert updated["settings"]["preferred_model"] == "ollama/llama3.2"
    assert updated["settings"]["preferred_voice_id"] == "elena-uk-f"
    assert updated["settings"]["preferred_tts_speed"] == 1.5

    # 3. Reject invalid font_id
    bad_res = test_client.patch(
        f"/api/v1/sessions/{session_id}/settings",
        json={"font_id": "nonexistent-font"},
    )
    assert bad_res.status_code == 422


def test_ai_providers_discovery_openrouter_and_ollama(client):
    test_client, _ = client
    res = test_client.get("/api/v1/models/providers?probe_ollama=false")
    assert res.status_code == 200
    data = res.json()
    assert data["openrouter"]["base_url"] == "https://openrouter.ai/api/v1"
    assert data["openrouter"]["free_router"] == "openrouter/free"
    assert data["openrouter"]["default_model"] == "openrouter/free"
    assert data["openrouter"]["supports_custom_model_id"] is True
    preset_ids = {m["id"] for m in data["preset_models"]}
    assert "openrouter/free" in preset_ids
    assert data["local_ai"]["ollama_base_url"] == "http://localhost:11434"
    assert data["local_ai"]["ollama_embedding_model"] == "nomic-embed-text"


def test_sqlalchemy_orm_models_and_exact_passage_offsets(client):
    _, SessionFactory = client
    full_text = (
        "Paragraph one explains how distraction-free extraction strips soft paywalls.\n\n"
        "Paragraph two proves that exact character offsets allow verifiable passage citations."
    )
    p2_text = "Paragraph two proves that exact character offsets allow verifiable passage citations."
    start_idx = full_text.index(p2_text)
    end_idx = start_idx + len(p2_text)

    with SessionFactory() as db:
        doc = Document(
            url="https://example.org/verifiable-rag",
            title="Verifiable Agentic RAG",
            author="Dr. Ada Lovelace",
            media_type="article",
            text_content=full_text,
            word_count=23,
            source_used="wayback",
        )
        db.add(doc)
        db.flush()

        chunk = PassageChunk(
            document_id=doc.id,
            paragraph_index=1,
            start_char=start_idx,
            end_char=end_idx,
            text=p2_text,
        )
        summary = SummaryRecord(
            document_id=doc.id,
            mode="tldr",
            provider="openrouter",
            model_id="deepseek/deepseek-r1",
            content="Exact character offsets guarantee verifiable citations.",
        )
        annotation = Annotation(
            document_id=doc.id,
            color="green",
            quote="exact character offsets allow verifiable passage citations",
            note="Critical for zero-hallucination research",
            start_char=start_idx,
            end_char=end_idx,
        )
        thread = ChatThread(
            document_id=doc.id,
            title="Offset Q&A",
            provider="ollama",
            model_id="llama3.2",
        )
        db.add_all([chunk, summary, annotation, thread])
        db.flush()

        msg = ChatMessage(
            thread_id=thread.id,
            role="assistant",
            content="The second paragraph proves exact character offset citations.",
            provider="ollama",
            model_id="llama3.2",
        )
        hist = ReadingHistory(
            document_id=doc.id,
            title=doc.title,
            url=doc.url,
            source_used="wayback",
            word_count=23,
        )
        feed = RssFeed(
            feed_url="https://example.org/feed.xml",
            title="AI Research Feed",
        )
        db.add_all([msg, hist, feed])
        db.flush()

        feed_item = RssFeedItem(
            feed_id=feed.id,
            document_id=doc.id,
            guid="item-001",
            title=doc.title,
            url=doc.url,
        )
        raw_key = "smry_live_testsecretkey123"
        api_key = ApiKey(
            name="Test Agent Key",
            key_prefix="smry_live_testse...",
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        )
        db.add_all([feed_item, api_key])
        db.commit()

        # Verify persisted relationships and exact character offset slice
        loaded_doc = db.get(Document, doc.id)
        assert loaded_doc is not None
        assert len(loaded_doc.passages) == 1
        saved_chunk = loaded_doc.passages[0]
        assert loaded_doc.text_content[saved_chunk.start_char : saved_chunk.end_char] == saved_chunk.text
        assert len(loaded_doc.summaries) == 1
        assert loaded_doc.summaries[0].provider == "openrouter"
        assert len(loaded_doc.annotations) == 1
        assert loaded_doc.annotations[0].color == "green"
        assert len(loaded_doc.chat_threads[0].messages) == 1
