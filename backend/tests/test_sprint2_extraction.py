"""
Sprint 2 Automated Test Suite:
Tests Distraction-Free HTML Sanitizer, Soft-Paywall Mirror Racing,
Copy-to-LLMs Markdown Exporter, YouTube Video Transcript Extraction,
and Book Ingestion (real PDF via PyMuPDF, real EPUB via ebooklib, and Markdown).
"""
import base64
import io
from ebooklib import epub
import pymupdf
import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.v1.extraction_router import get_http_client
from app.db.session import get_db, get_engine, get_session_factory, init_db
from app.extraction.sanitizer import sanitize_and_extract_html
from app.extraction.youtube import parse_youtube_video_id
from app.main import create_app


@pytest.fixture()
def sprint2_client(tmp_path):
    db_file = tmp_path / "test_sprint2.db"
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
        yield app, test_client


def test_distraction_and_paywall_stripper():
    noisy_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Agentic Verification Architecture | ScienceDaily</title>
        <meta name="author" content="Dr. Elena Vance" />
        <meta property="og:site_name" content="ScienceDaily" />
      </head>
      <body>
        <div id="onetrust-cookie-banner" class="gdpr-consent">Accept all cookies to continue</div>
        <div class="paywall-overlay subscribe-wall">Subscribe to continue reading this article</div>
        <aside class="ad-container">Sponsored Advertisement Banner</aside>
        <article style="filter: blur(5px); overflow: hidden;">
          <h1>Agentic Verification Architecture</h1>
          <p>Autonomous research agents require deterministic passage indexing to verify every claim against primary literature.</p>
          <div class="newsletter-modal">Sign up for our weekly AI newsletter!</div>
          <p>Empirical evaluations across ten thousand citations show that exact character offset verification eliminates fabricated quotes.</p>
        </article>
        <script>window.triggerPaywallModal();</script>
      </body>
    </html>
    """
    extracted = sanitize_and_extract_html(noisy_html, url="https://sciencedaily.example/agentic-verification")
    assert extracted["title"] == "Agentic Verification Architecture"
    assert extracted["author"] == "Dr. Elena Vance"
    assert extracted["site_name"] == "ScienceDaily"
    assert extracted["stripped_elements_count"] >= 4
    assert "Accept all cookies" not in extracted["text_content"]
    assert "Sponsored Advertisement" not in extracted["text_content"]
    assert "weekly AI newsletter" not in extracted["text_content"]
    assert "deterministic passage indexing" in extracted["text_content"]
    assert "# Agentic Verification Architecture" in extracted["llm_markdown"]

    # Verify exact character offsets invariant: text_content[start_char:end_char] == text
    assert len(extracted["passages"]) == 2
    for p in extracted["passages"]:
        assert extracted["text_content"][p["start_char"] : p["end_char"]] == p["text"]


def test_multi_source_mirror_racing_selects_unblocked_version(sprint2_client):
    app, client = sprint2_client

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "web.archive.org" in url_str:
            return httpx.Response(
                200,
                text="""
                <html>
                  <head><title>Full Unblocked Climate Report</title></head>
                  <body>
                    <article>
                      <h1>Full Unblocked Climate Report</h1>
                      <p>This complete investigative article was recovered from the Wayback Machine mirror without any soft paywall truncation.</p>
                      <p>Satellite spectrometry across twelve orbital sensors confirmed a 42 percent reduction in industrial methane plumes.</p>
                      <p>Independent ground stations validated the measurements across three continents over a twenty-four month period.</p>
                    </article>
                  </body>
                </html>
                """,
            )
        # Direct and other mirrors return a truncated soft-paywall stub
        return httpx.Response(
            200,
            text="""
            <html>
              <head><title>Full Unblocked Climate Report</title></head>
              <body>
                <article>
                  <p>Subscribe to continue reading. You have reached your free article limit.</p>
                </article>
              </body>
            </html>
            """,
        )

    mock_async_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    app.dependency_overrides[get_http_client] = lambda: mock_async_client

    try:
        res = client.post(
            "/api/v1/extract/url",
            json={
                "url": "https://news.example.org/climate-report",
                "source": "auto",
                "save_to_library": True,
                "tags": ["climate", "investigation"],
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["source_used"] == "wayback"
        assert "42 percent reduction in industrial methane plumes" in data["text_content"]
        assert any(a["source"] == "wayback" and a["selected"] is True for a in data["source_attempts"])

        # Test Copy to LLMs endpoint on persisted document
        doc_id = data["id"]
        llm_res = client.get(f"/api/v1/documents/{doc_id}/copy-to-llm")
        assert llm_res.status_code == 200
        llm_data = llm_res.json()
        assert "Extracted Via:** `wayback`" in llm_data["llm_markdown"]
        assert "42 percent reduction" in llm_data["llm_markdown"]
    finally:
        app.dependency_overrides.pop(get_http_client, None)


def test_youtube_transcript_extraction_and_endpoint(sprint2_client):
    app, client = sprint2_client

    assert parse_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://youtu.be/abc123XYZ99") == "abc123XYZ99"
    assert parse_youtube_video_id("https://www.youtube.com/shorts/short98765") == "short98765"

    def mock_yt_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "youtube.com/watch" in url_str:
            return httpx.Response(
                200,
                text="""
                <html>
                  <head><title>LangGraph Multi-Agent Architecture Explained - YouTube</title></head>
                  <body>
                    <script>
                      var ytInitialPlayerResponse = {
                        "videoDetails": {"ownerChannelName": "AI Systems Lab"},
                        "captions": {
                          "playerCaptionsTracklistRenderer": {
                            "captionTracks": [
                              {"baseUrl": "https://www.youtube.com/api/timedtext?v=lg12345", "languageCode": "en"}
                            ]
                          }
                        }
                      };
                    </script>
                  </body>
                </html>
                """,
            )
        if "api/timedtext" in url_str:
            return httpx.Response(
                200,
                text="""
                <transcript>
                  <text start="0.0" dur="6.5">Welcome to our deep dive on stateful multi-agent orchestration with LangGraph.</text>
                  <text start="6.5" dur="8.0">Every agent node inspects and updates a typed state graph with cyclic verification.</text>
                </transcript>
                """,
            )
        return httpx.Response(404)

    mock_async_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_yt_handler))
    app.dependency_overrides[get_http_client] = lambda: mock_async_client

    try:
        res = client.post(
            "/api/v1/extract/youtube",
            json={
                "url": "https://www.youtube.com/watch?v=lg12345",
                "languages": ["en"],
                "save_to_library": True,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["media_type"] == "youtube"
        assert data["title"] == "LangGraph Multi-Agent Architecture Explained"
        assert data["author"] == "AI Systems Lab"
        assert len(data["transcript_segments"]) == 2
        assert "[00:00] Welcome to our deep dive" in data["text_content"]
        assert "[00:06] Every agent node inspects" in data["text_content"]
        assert data["passages"][1]["page_or_timestamp"] == "00:06"
    finally:
        app.dependency_overrides.pop(get_http_client, None)


def test_pdf_epub_and_markdown_book_ingestion(sprint2_client):
    _, client = sprint2_client

    # 1. Create a real 2-page PDF in memory with PyMuPDF
    pdf_doc = pymupdf.open()
    p1 = pdf_doc.new_page()
    p1.insert_text((72, 72), "Chapter 1: Quantum Error Correction.\n\nSurface codes protect logical qubits against local noise.")
    p2 = pdf_doc.new_page()
    p2.insert_text((72, 72), "Chapter 2: Neutral Atom Arrays.\n\nOptical tweezers enable transversal gates with 99.9% fidelity.")
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    pdf_res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Quantum Computing Handbook",
            "author": "Dr. Richard Feynman",
            "format": "pdf",
            "file_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            "save_to_library": True,
            "tags": ["quantum", "book"],
        },
    )
    assert pdf_res.status_code == 201
    pdf_data = pdf_res.json()
    assert pdf_data["media_type"] == "book"
    assert pdf_data["source_used"] == "pdf-parser"
    assert "Surface codes protect logical qubits" in pdf_data["text_content"]
    assert "99.9% fidelity" in pdf_data["text_content"]
    assert any(p["page_or_timestamp"] == "Page 2" for p in pdf_data["passages"])

    # 2. Create a real EPUB book in memory with ebooklib
    book = epub.EpubBook()
    book.set_identifier("id_epub_test_001")
    book.set_title("Distributed Systems Architecture")
    book.set_language("en")
    book.add_author("Dr. Leslie Lamport")

    ch1 = epub.EpubHtml(title="Consensus Protocols", file_name="chap_01.xhtml", lang="en")
    ch1.content = (
        "<html><body><h1>Chapter 1: Consensus Protocols</h1>"
        "<p>Paxos and Raft guarantee safety under asynchronous network partitions.</p>"
        "</body></html>"
    )
    book.add_item(ch1)
    book.toc = (epub.Link("chap_01.xhtml", "Consensus Protocols", "ch1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch1]

    epub_buf = io.BytesIO()
    epub.write_epub(epub_buf, book)
    epub_bytes = epub_buf.getvalue()

    epub_res = client.post(
        "/api/v1/extract/book",
        json={
            "title": "Distributed Systems Architecture",
            "author": "Dr. Leslie Lamport",
            "format": "epub",
            "file_base64": base64.b64encode(epub_bytes).decode("ascii"),
            "save_to_library": True,
        },
    )
    assert epub_res.status_code == 201
    epub_data = epub_res.json()
    assert epub_data["source_used"] == "epub-parser"
    assert "Paxos and Raft guarantee safety" in epub_data["text_content"]
    assert epub_data["passages"][0]["page_or_timestamp"] == "Chapter 1: Consensus Protocols"
