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


def test_redirect_interstitial_page_not_selected(sprint2_client):
    """Google cache may return a search redirect page instead of the cached article.
    Redirect/interstitial pages must be detected and not chosen as the winner when
    a real article mirror is available.
    """
    app, client = sprint2_client

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "webcache.googleusercontent.com" in url_str:
            # Google cache is dead; returns a Google Search interstitial page
            return httpx.Response(
                200,
                text="""
                <html>
                  <head><title>Google Search</title></head>
                  <body>
                    <p>Please click here if you are not redirected within a few seconds.</p>
                    <p>If you're having trouble accessing Google Search, please click here , or send feedback .</p>
                  </body>
                </html>
                """,
            )
        # Direct and wayback return a real article
        return httpx.Response(
            200,
            text="""
            <html>
              <head><title>Real Climate Report</title></head>
              <body>
                <article>
                  <h1>Real Climate Report</h1>
                  <p>This is a full investigative article about climate policy with substantive analysis and data.</p>
                  <p>Satellite spectrometry across twelve orbital sensors confirmed a 42 percent reduction in industrial methane plumes over twenty-four months.</p>
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
            },
        )
        assert res.status_code == 201
        data = res.json()
        # The real article (direct or wayback) must win, not the googlecache redirect
        assert data["source_used"] != "googlecache", "Google cache redirect page must not be selected"
        assert "42 percent reduction" in data["text_content"]

        # The googlecache attempt should be flagged as a redirect and score 0 (excluded)
        gcache_attempt = next(
            (a for a in data["source_attempts"] if a["source"] == "googlecache"), None
        )
        assert gcache_attempt is not None
        assert gcache_attempt["selected"] is False
        assert gcache_attempt["score"] == 0.0
    finally:
        app.dependency_overrides.pop(get_http_client, None)


def test_all_mirrors_redirect_raises_runtime_error(sprint2_client):
    """If every mirror returns a redirect/interstitial page, extraction must fail
    rather than return garbage content."""
    app, client = sprint2_client

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="""
            <html>
              <head><title>Google Search</title></head>
              <body>
                <p>Please click here if you are not redirected within a few seconds.</p>
                <p>send feedback .</p>
              </body>
            </html>
            """,
        )

    mock_async_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    app.dependency_overrides[get_http_client] = lambda: mock_async_client

    try:
        res = client.post(
            "/api/v1/extract/url",
            json={"url": "https://news.example.org/climate-report", "source": "auto"},
        )
        assert res.status_code == 502
        assert "Unable to extract readable content" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_http_client, None)


def test_sanitizer_strips_npr_style_chrome():
    """NPR article HTML contains heavy navigation chrome (global nav, footer links,
    'More Stories', 'Popular on', cookie settings modals, audio player chrome).
    The sanitizer must strip all of this and leave only the article body."""
    noisy_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>The leader of a Kenyan doomsday cult is sentenced to 200 years in prison</title>
        <meta property="og:title" content="The leader of a Kenyan doomsday cult is sentenced to 200 years in prison" />
        <meta name="author" content="The Associated Press" />
        <meta property="og:site_name" content="NPR" />
        <meta property="article:published_time" content="2026-11-06T09:53:46-05:00" />
      </head>
      <body>
        <!-- Site navigation chrome -->
        <header class="global-nav">
          <div class="npr-logo">NPR</div>
          <nav class="main-nav">
            <ul><li><a href="/">Home</a></li><li><a href="/news">News</a></li></ul>
          </nav>
        </header>

        <!-- Cookie settings modal -->
        <div class="cookie-settings consent-modal" role="dialog">
          <h2>Cookie Settings</h2>
          <p>When you visit our website we store cookies...</p>
          <button>Allow All</button>
          <button>Manage Consent Preferences</button>
        </div>

        <!-- Audio player chrome -->
        <div class="audio-player">
          <span>Skip to main content</span>
          <span>Keyboard shortcuts for audio player</span>
          <div>Play Live Radio</div>
        </div>

        <article>
          <h1>The leader of a Kenyan doomsday cult is sentenced to 200 years in prison</h1>
          <p>MOMBASA, Kenya — The leader of a Kenyan doomsday cult linked to the deaths of more than 400 people was sentenced on Friday to 200 years in prison for the murders of 191 people.</p>
          <p>The High Court in Kenya's coastal city of Mombasa issued the sentence for Pastor Paul Mackenzie.</p>
        </article>

        <!-- Footer chrome -->
        <footer class="footer-nav">
          <div class="more-stories">
            <h3>More Stories From NPR</h3>
            <ul><li><a href="/story1">Story 1</a></li></ul>
          </div>
          <div class="popular-on">
            <h3>Popular on NPR.org</h3>
            <ul><li><a href="/story2">Story 2</a></li></ul>
          </div>
        </footer>
      </body>
    </html>
    """

    extracted = sanitize_and_extract_html(noisy_html, url="https://www.npr.org/2026/11/06/nx-s1-6032593/kenya-cult-leader-paul-mackenzie-sentenced-murder")

    # Article title and metadata preserved
    assert "The leader of a Kenyan doomsday cult" in extracted["title"]
    assert extracted["site_name"] == "NPR"
    assert extracted["author"] == "The Associated Press"

    # Article body preserved
    assert "MOMBASA, Kenya" in extracted["text_content"]
    assert "Pastor Paul Mackenzie" in extracted["text_content"]
    assert "200 years in prison" in extracted["text_content"]

    # Chrome stripped: navigation, cookie modal, audio player, footer
    assert "Cookie Settings" not in extracted["text_content"]
    assert "Allow All" not in extracted["text_content"]
    assert "Manage Consent Preferences" not in extracted["text_content"]
    assert "Skip to main content" not in extracted["text_content"]
    assert "Keyboard shortcuts" not in extracted["text_content"]
    assert "Play Live Radio" not in extracted["text_content"]
    assert "More Stories From NPR" not in extracted["text_content"]
    assert "Popular on NPR.org" not in extracted["text_content"]
    assert "NPR" not in extracted["text_content"] or extracted["text_content"].count("NPR") <= 1

    # stripped_elements_count should reflect removed chrome
    assert extracted["stripped_elements_count"] >= 5


def test_bot_challenge_page_rejected_in_race(sprint2_client):
    """Direct fetch on JS-heavy sites returns anti-bot interstitials ('JavaScript is
    disabled', 'A required part of this site couldn't load'). These must score 0 and
    never win the race when a real mirror is available."""
    app, client = sprint2_client

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "web.archive.org" in url_str:
            return httpx.Response(
                200,
                text="""
                <html>
                  <head><title>Archived Full Article</title></head>
                  <body>
                    <article>
                      <h1>Archived Full Article</h1>
                      <p>The archived mirror serves the complete investigative text without any bot challenge or truncation whatsoever.</p>
                      <p>Independent verification confirmed every quoted measurement across three separate continental reporting stations.</p>
                    </article>
                  </body>
                </html>
                """,
            )
        # Direct and jina serve anti-bot JS-required interstitials
        return httpx.Response(
            200,
            text="""
            <html>
              <head><title>Access Denied</title></head>
              <body>
                <noscript>JavaScript is disabled in your browser. Please enable JavaScript to proceed.</noscript>
                <p>A required part of this site couldn't load. This may be due to a browser extension, network issues, or browser settings. Please check your connection, disable any ad blockers, or try using a different browser.</p>
              </body>
            </html>
            """,
        )

    mock_async_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    app.dependency_overrides[get_http_client] = lambda: mock_async_client

    try:
        res = client.post(
            "/api/v1/extract/url",
            json={"url": "https://news.example.org/bot-guarded-story", "source": "auto"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["source_used"] == "wayback"
        assert "JavaScript is disabled" not in data["text_content"]

        direct_attempt = next(a for a in data["source_attempts"] if a["source"] == "direct")
        assert direct_attempt["score"] == 0.0
        assert direct_attempt["selected"] is False
    finally:
        app.dependency_overrides.pop(get_http_client, None)


def test_sanitizer_strips_js_challenge_boilerplate_paragraphs():
    """When a challenge page shares the DOM with real content, the challenge
    paragraphs must be stripped from text_content."""
    mixed_html = """
    <html><body>
      <article>
        <p>JavaScript is disabled in your browser. Please enable JavaScript to proceed.</p>
        <p>The genuine article body begins here with substantive analytical reporting content.</p>
        <p>A required part of this site couldn't load. This may be due to a browser extension, network issues.</p>
        <p>More genuine analysis follows with additional verified factual claims and sourced quotations.</p>
      </article>
    </body></html>
    """
    extracted = sanitize_and_extract_html(mixed_html, url="https://example.org/mixed")
    assert "JavaScript is disabled" not in extracted["text_content"]
    assert "couldn't load" not in extracted["text_content"]
    assert "genuine article body" in extracted["text_content"]
    assert extracted["redirect_detected"] is True


@pytest.mark.parametrize("image", ["http://[broken", "https://[invalid]/image.jpg", "/image.jpg", "javascript:alert(1)"])
def test_optional_image_url_validation(image):
    html = f'''<html><head><meta property="og:image" content="{image}"></head>
    <body><article><h1>Article title</h1><p>Article text survives malformed image metadata.</p></article></body></html>'''
    result = sanitize_and_extract_html(html, url="https://example.com/story")
    assert "Article text survives" in result["text_content"]
    assert result["image_url"] == ("https://example.com/image.jpg" if image == "/image.jpg" else None)
