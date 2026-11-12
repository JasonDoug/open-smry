"""
Automatic Multi-Source Selection & Mirror Racing Engine.
Concurrently races Direct Fetch, Wayback Machine, Google Cache / Archive mirrors,
and Reader Proxy in parallel using asyncio + httpx, scoring each candidate by
completeness, paragraph density, and absence of soft-paywall markers.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import re
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

    if candidate.get("redirect_detected"):
        score -= 200.0

    for rx in PAYWALL_BOILERPLATE_PATTERNS:
        if rx.search(text_content):
            score -= 160.0

    if word_count < 15:
        score -= 45.0

    # Reject token/redirect boilerplate pages masquerading as articles.
    if word_count < 40 and passage_count <= 1:
        score -= 120.0

    return round(max(0.0, score), 2)


def _wrap_plain_text_as_html(raw_text: str, title: str = "Extracted Article") -> str:
    paras = [
        f"<p>{html_lib.escape(p.strip())}</p>"
        for p in raw_text.split("\n\n")
        if p.strip()
    ]
    return f"<html><head><title>{html_lib.escape(title)}</title></head><body><article>{''.join(paras)}</article></body></html>"


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_MD_BULLET_RE = re.compile(r"^[*+-]\s+")
_MD_RULE_RE = re.compile(r"^(?:[*_-]\s*){3,}$")
_JINA_HEADER_RE = re.compile(r"^(Title|URL Source|Published Time):\s*(.*)$")


def parse_jina_reader_output(raw_text: str, target_url: str) -> tuple[str, bool]:
    """
    Converts r.jina.ai reader output (a ``Title:/URL Source:/Published Time:``
    header followed by ``Markdown Content:``) into minimal HTML for the sanitizer.

    - Header fields become <title>/og:title and article:published_time metadata.
    - Images are dropped and links are flattened to their anchor text.
    - Blocks made almost entirely of links (site navigation, "Most Read" rails)
      are dropped.
    - When a subscription-wall prompt appears, everything after it is page
      chrome (the article was cut off), so the body is truncated there and the
      result is flagged as a paywalled preview.

    Returns ``(html, paywall_truncated)``.
    """
    header: Dict[str, str] = {}
    body = raw_text
    marker = "Markdown Content:"
    if marker in raw_text:
        head, body = raw_text.split(marker, 1)
        for line in head.splitlines():
            m = _JINA_HEADER_RE.match(line.strip())
            if m:
                header[m.group(1)] = m.group(2).strip()

    title = header.get("Title") or target_url
    published = header.get("Published Time")
    blocks: List[str] = []
    paywall_truncated = False

    for raw_block in re.split(r"\n\s*\n", body):
        block = raw_block.strip()
        if not block or _MD_RULE_RE.match(block):
            continue
        no_images = _MD_IMAGE_RE.sub("", block)
        flattened = _MD_LINK_RE.sub(r"\1", no_images).strip()
        if any(rx.search(flattened) for rx in PAYWALL_BOILERPLATE_PATTERNS):
            paywall_truncated = True
            break
        # Text that is NOT inside a link: if (almost) none, it's a link rail.
        unlinked = _MD_LINK_RE.sub("", no_images)
        unlinked = re.sub(r"[*•|\-\s]+", " ", unlinked).strip()
        if no_images != block or _MD_LINK_RE.search(no_images):
            # Keep bylines ("By [Name](...)"), drop pure link rails.
            if len(unlinked.split()) < 3 and not re.match(r"^By\b", flattened):
                continue
        if not flattened:
            continue
        line = re.sub(r"\s+", " ", flattened)
        heading = _MD_HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{html_lib.escape(heading.group(2))}</h{level}>")
        elif _MD_BULLET_RE.match(line):
            blocks.append(f"<li>{html_lib.escape(_MD_BULLET_RE.sub('', line))}</li>")
        else:
            blocks.append(f"<p>{html_lib.escape(line.strip('*_ '))}</p>")

    meta = f'<meta property="og:title" content="{html_lib.escape(title, quote=True)}">'
    if published:
        meta += f'<meta property="article:published_time" content="{html_lib.escape(published, quote=True)}">'
    html = (
        f"<html><head><title>{html_lib.escape(title)}</title>{meta}</head>"
        f"<body><article>{''.join(blocks)}</article></body></html>"
    )
    return html, paywall_truncated


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


WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available"


async def _wayback_snapshot_url(
    client: httpx.AsyncClient, target_url: str, timeout_sec: float
) -> Optional[str]:
    """
    Asks the Wayback availability API for the closest snapshot of `target_url`.

    The `/web/2/<url>` shortcut can transiently 404 for fresh captures that the
    availability index already lists, so this is used as a fallback.
    """
    try:
        resp = await client.get(
            WAYBACK_AVAILABILITY_API, params={"url": target_url}, timeout=timeout_sec
        )
        closest = (resp.json().get("archived_snapshots") or {}).get("closest") or {}
    except Exception:
        return None
    snap = closest.get("url")
    if not closest.get("available") or not isinstance(snap, str):
        return None
    if not snap.startswith("http://web.archive.org/") and not snap.startswith("https://web.archive.org/"):
        return None
    return "https://" + snap.split("://", 1)[1]


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
        if source_id == "wayback" and resp.status_code == 404:
            snapshot_url = await _wayback_snapshot_url(client, target_url, timeout_sec)
            if snapshot_url:
                resp = await client.get(snapshot_url, headers=BROWSER_HEADERS, timeout=timeout_sec)
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
        paywall_truncated = False
        if provider.get("is_plain_text") and "<html" not in raw_body.lower():
            if "Markdown Content:" in raw_body:
                raw_body, paywall_truncated = parse_jina_reader_output(raw_body, target_url)
            else:
                raw_body = _wrap_plain_text_as_html(raw_body, target_url)

        extracted = sanitize_and_extract_html(raw_body, url=target_url, source_used=source_id)
        if paywall_truncated:
            extracted["paywall_detected"] = True
            # Real article lede cut off at a subscription prompt (not a captcha page).
            extracted["paywall_preview"] = True
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
        a
        for a in attempts
        if a.get("document") and a.get("word_count", 0) > 0 and a.get("score", 0) > 0
    ]
    valid_attempts.sort(key=lambda a: (-a["score"], a["latency_ms"]))

    if not valid_attempts:
        # Nothing scored above zero, but a flagged paywall preview is still more
        # useful than an error: return it so the reader can label it as such.
        previews = [
            a
            for a in attempts
            if a.get("document")
            and a["document"].get("paywall_preview")
            and a.get("word_count", 0) > 0
        ]
        previews.sort(key=lambda a: (-a["word_count"], a["latency_ms"]))
        valid_attempts = previews[:1]

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
