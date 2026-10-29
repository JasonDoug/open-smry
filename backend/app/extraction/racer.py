"""
Automatic Multi-Source Selection & Mirror Racing Engine.
Concurrently races Direct Fetch, Wayback Machine, Google Cache / Archive mirrors,
and Reader Proxy in parallel using asyncio + httpx, scoring each candidate by
completeness, paragraph density, and absence of soft-paywall markers.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

import httpx

from app.extraction.sanitizer import (
    PAYWALL_BOILERPLATE_PATTERNS,
    format_copy_to_llm_markdown,
    sanitize_and_extract_html,
)
from app.extraction.youtube import (
    extract_youtube_transcript,
    parse_youtube_video_id,
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def score_extraction_candidate(candidate: Optional[Dict[str, Any]]) -> float:
    """
    Scores an extracted article candidate to pick the most complete, unblocked version
    during multi-source mirror racing.
    """
    if not candidate or not candidate.get("text_content"):
        return 0.0

    word_count = int(candidate.get("word_count", 0))
    passage_count = len(candidate.get("passages") or [])
    text_content = str(candidate.get("text_content", ""))

    score = min(word_count, 5000) * 0.5 + min(passage_count, 60) * 6.0

    if candidate.get("paywall_detected"):
        score -= 160.0

    for rx in PAYWALL_BOILERPLATE_PATTERNS:
        if rx.search(text_content):
            score -= 160.0

    if word_count < 15:
        score -= 45.0

    return round(max(0.0, score), 2)


def _wrap_plain_text_as_html(raw_text: str, title: str = "Extracted Article") -> str:
    paras = [
        f"<p>{html_lib.escape(p.strip())}</p>"
        for p in raw_text.split("\n\n")
        if p.strip()
    ]
    return f"<html><head><title>{html_lib.escape(title)}</title></head><body><article>{''.join(paras)}</article></body></html>"


MIRROR_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "direct",
        "build_url": lambda u: u,
        "is_plain_text": False,
    },
    {
        "id": "wayback",
        "build_url": lambda u: f"https://web.archive.org/web/2/{u}",
        "is_plain_text": False,
    },
    {
        "id": "googlecache",
        "build_url": lambda u: f"https://webcache.googleusercontent.com/search?q=cache:{quote(u, safe='')}&strip=1",
        "is_plain_text": False,
    },
    {
        "id": "jina",
        "build_url": lambda u: f"https://r.jina.ai/{u}",
        "is_plain_text": True,
    },
]


async def _probe_single_mirror(
    provider: Dict[str, Any],
    target_url: str,
    client: httpx.AsyncClient,
    timeout_sec: float,
) -> Dict[str, Any]:
    source_id = provider["id"]
    req_url = provider["build_url"](target_url)
    start_ts = time.perf_counter()

    try:
        resp = await client.get(req_url, headers=BROWSER_HEADERS, timeout=timeout_sec)
        latency_ms = int((time.perf_counter() - start_ts) * 1000)

        if resp.status_code != 200 or not resp.text.strip():
            return {
                "source": source_id,
                "status": f"http_{resp.status_code}",
                "word_count": 0,
                "score": 0.0,
                "latency_ms": latency_ms,
                "document": None,
            }

        raw_body = resp.text
        if provider.get("is_plain_text") and "<html" not in raw_body.lower():
            raw_body = _wrap_plain_text_as_html(raw_body, target_url)

        extracted = sanitize_and_extract_html(raw_body, url=target_url, source_used=source_id)
        score = score_extraction_candidate(extracted)
        return {
            "source": source_id,
            "status": "ok",
            "word_count": extracted["word_count"],
            "score": score,
            "latency_ms": latency_ms,
            "document": extracted,
        }
    except httpx.TimeoutException:
        return {
            "source": source_id,
            "status": "timeout",
            "word_count": 0,
            "score": 0.0,
            "latency_ms": int((time.perf_counter() - start_ts) * 1000),
            "document": None,
        }
    except Exception:
        return {
            "source": source_id,
            "status": "error",
            "word_count": 0,
            "score": 0.0,
            "latency_ms": int((time.perf_counter() - start_ts) * 1000),
            "document": None,
        }


async def extract_from_url(
    url: str,
    *,
    preferred_source: str = "auto",
    raw_html_override: Optional[str] = None,
    timeout_sec: float = 6.5,
    http_client: Optional[httpx.AsyncClient] = None,
    transcript_fetcher: Optional[Callable[[str, List[str]], List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Races multiple web mirrors (or extracts YouTube transcripts / raw HTML overrides)
    and returns the most complete, unblocked version of the article along with
    full source_attempts telemetry.
    """
    normalized_url = (url or "").strip()
    if not normalized_url and not raw_html_override:
        raise ValueError("Either 'url' or 'raw_html_override' must be provided.")

    # 1. Check if YouTube Video URL
    if normalized_url and parse_youtube_video_id(normalized_url):
        return await extract_youtube_transcript(
            normalized_url,
            http_client=http_client,
            transcript_fetcher=transcript_fetcher,
        )

    # 2. Check if raw_html_override was provided directly
    if raw_html_override:
        doc = sanitize_and_extract_html(
            raw_html_override,
            url=normalized_url or "local://raw-html",
            source_used="direct-html",
        )
        score = score_extraction_candidate(doc)
        doc["source_score"] = score
        doc["source_attempts"] = [
            {
                "source": "direct-html",
                "status": "ok",
                "word_count": doc["word_count"],
                "score": score,
                "latency_ms": 1,
                "selected": True,
            }
        ]
        return doc

    # 3. Select mirrors to race
    if preferred_source and preferred_source != "auto":
        providers = [p for p in MIRROR_PROVIDERS if p["id"] == preferred_source]
        if not providers:
            providers = MIRROR_PROVIDERS
    else:
        providers = MIRROR_PROVIDERS

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(follow_redirects=True)
    try:
        attempts = await asyncio.gather(
            *[
                _probe_single_mirror(prov, normalized_url, client, timeout_sec)
                for prov in providers
            ]
        )
    finally:
        if owns_client:
            await client.aclose()

    valid_attempts = [
        a for a in attempts if a.get("document") and a.get("word_count", 0) > 0
    ]
    valid_attempts.sort(key=lambda a: (-a["score"], a["latency_ms"]))

    if not valid_attempts:
        raise RuntimeError(
            f"Unable to extract readable content from '{normalized_url}' across {len(attempts)} mirror(s)."
        )

    winner = valid_attempts[0]
    winning_doc: Dict[str, Any] = winner["document"]
    winning_doc["source_used"] = winner["source"]
    winning_doc["source_score"] = winner["score"]
    winning_doc["llm_markdown"] = format_copy_to_llm_markdown(
        title=winning_doc["title"],
        url=winning_doc["url"],
        author=winning_doc.get("author"),
        site_name=winning_doc.get("site_name"),
        published_time=winning_doc.get("published_time"),
        source_used=winner["source"],
        word_count=winning_doc["word_count"],
        reading_time_minutes=winning_doc["reading_time_minutes"],
        markdown_body=winning_doc["markdown"],
    )
    winning_doc["source_attempts"] = [
        {
            "source": a["source"],
            "status": a["status"],
            "word_count": a["word_count"],
            "score": a["score"],
            "latency_ms": a["latency_ms"],
            "selected": a["source"] == winner["source"],
        }
        for a in attempts
    ]
    return winning_doc
