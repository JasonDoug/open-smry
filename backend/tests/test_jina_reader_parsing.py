"""
Jina reader (r.jina.ai) output parsing & paywall-preview detection (BUG-029):
- Header fields (Title / Published Time) become document metadata.
- Navigation link rails and images are dropped; links flatten to anchor text.
- Content after a subscription-wall prompt is truncated and flagged.
"""
from __future__ import annotations

import httpx
import pytest

from app.extraction.racer import extract_from_url, parse_jina_reader_output
from app.extraction.sanitizer import sanitize_and_extract_html

URL = "https://news.example.com/politics/2026/11/11/sample-story/"

PAYWALLED_JINA = f"""Title: Sample headline about oversight fights

URL Source: {URL}

Published Time: 2026-11-11T16:00:17.367Z

Markdown Content:
[Accessibility statement](https://news.example.com/accessibility/)[Skip to main content]({URL}#main)

[Politics](https://news.example.com/politics/)[White House](https://news.example.com/wh/)[Courts & Law](https://news.example.com/law/)

# Sample headline about oversight fights

A one-sentence dek describing the strategy taking shape this week.

![Image 4](https://news.example.com/img/photo.jpg)

A caption describing the photo of officials meeting in the office. (Photo Agency)

By [Jane Reporter](https://news.example.com/people/jane/)

The administration has started staffing up its legal office with additional hires as it prepares for a surge of oversight requests.

Subscribe for unlimited access to The Post

You can cancel anytime.

Most Read

* [Unrelated trending story one](https://news.example.com/a) * [Unrelated trending story two](https://news.example.com/b)
"""


def test_parse_jina_extracts_metadata_and_drops_link_rails() -> None:
    """Header metadata is applied; nav rails, images and post-wall chrome are removed."""
    html, truncated = parse_jina_reader_output(PAYWALLED_JINA, URL)
    assert truncated is True
    doc = sanitize_and_extract_html(html, url=URL, source_used="jina")
    assert doc["title"] == "Sample headline about oversight fights"
    assert doc["published_time"] == "2026-11-11T16:00:17.367Z"
    text = doc["text_content"]
    assert "staffing up its legal office" in text
    assert "By Jane Reporter" in text
    for chrome in ("Accessibility statement", "Courts & Law", "Most Read",
                   "Unrelated trending", "cancel anytime", "Image 4", "https://"):
        assert chrome not in text


def test_parse_jina_full_article_not_flagged() -> None:
    """Without a subscription prompt, the full body is kept and not flagged."""
    full = PAYWALLED_JINA.split("Subscribe for unlimited access")[0] + (
        "A second full paragraph continues the reporting with more detail.\n"
    )
    html, truncated = parse_jina_reader_output(full, URL)
    assert truncated is False
    doc = sanitize_and_extract_html(html, url=URL, source_used="jina")
    assert "second full paragraph" in doc["text_content"]


@pytest.mark.asyncio
async def test_racer_flags_jina_paywall_preview() -> None:
    """A Jina paywalled preview is flagged and penalized when it wins the race."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(200, text=PAYWALLED_JINA)
        return httpx.Response(404, text="")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        doc = await extract_from_url(URL, http_client=client)
    assert doc["source_used"] == "jina"
    assert doc["paywall_detected"] is True
    assert doc["title"] == "Sample headline about oversight fights"
    jina = next(a for a in doc["source_attempts"] if a["source"] == "jina")
    assert jina["selected"] is True


@pytest.mark.asyncio
async def test_wayback_falls_back_to_availability_snapshot() -> None:
    """A transient /web/2/ 404 falls back to the snapshot listed by the availability API."""
    snapshot = f"http://web.archive.org/web/20261111224020/{URL}"
    article = (
        "<html><head><title>Archived headline</title></head><body><article>"
        + "".join(f"<p>Archived paragraph {i} with enough words to count as real content.</p>" for i in range(12))
        + "</article></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "archive.org" and request.url.path == "/wayback/available":
            return httpx.Response(200, json={"archived_snapshots": {"closest": {
                "available": True, "status": "200", "url": snapshot}}})
        if request.url.host == "web.archive.org":
            if request.url.path.startswith("/web/2/"):
                return httpx.Response(404, text="not found")
            if request.url.path.startswith("/web/20261111224020/"):
                return httpx.Response(200, text=article)
        return httpx.Response(404, text="")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        doc = await extract_from_url(URL, http_client=client)
    assert doc["source_used"] == "wayback"
    assert "Archived paragraph 11" in doc["text_content"]
    assert doc["paywall_detected"] is False
