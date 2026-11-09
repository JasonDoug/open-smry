"""
Distraction-Free HTML Sanitizer, Soft-Paywall Stripper, Passage Offset Chunker,
and Copy-to-LLMs Markdown Exporter.
Uses BeautifulSoup4 (lxml), trafilatura, and readability-lxml.
"""
from __future__ import annotations

import html as html_lib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Comment, Tag
import trafilatura
from readability import Document as ReadabilityDocument

DISTRACTION_KEYWORDS_RE = re.compile(
    r"\b("
    r"paywall|cookie|cookie-banner|cookie-consent|gdpr|onetrust|cybotcookiebot|"
    r"newsletter-modal|newsletter-signup|subscribe-wall|subscription-wall|"
    r"meter-wall|piano-modal|reg-wall|registration-wall|ad-container|"
    r"ad-slot|ad-wrapper|advertisement|sponsored-box|popup-overlay|"
    r"modal-backdrop|share-bar|social-share|related-posts|outbrain|taboola|"
    r"global-nav|main-nav|site-nav|navigation|nav-menu|utility-nav|"
    r"footer-nav|more-stories|popular-on|editors-picks|recommended|trending|"
    r"cookie-settings|consent-modal|opt-out|targeting-sponsor|"
    r"npr-plus|sponsor-message|audio-player|skip-to-main|keyboard-shortcut"
    r")\b",
    re.IGNORECASE,
)

PAYWALL_BOILERPLATE_PATTERNS = [
    re.compile(r"subscribe to continue reading", re.IGNORECASE),
    re.compile(r"you have reached your free article limit", re.IGNORECASE),
    re.compile(r"this article is for subscribers only", re.IGNORECASE),
    re.compile(r"please enable javascript and disable any ad blocker", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"create a free account to continue reading", re.IGNORECASE),
]

REDIRECT_INTERSTITIAL_PATTERNS = [
    re.compile(r"please click here if you are not redirected", re.IGNORECASE),
    re.compile(r"having trouble accessing google search", re.IGNORECASE),
    re.compile(r"send feedback\s*\.\s*$", re.IGNORECASE),
    re.compile(r"google search", re.IGNORECASE),
    re.compile(r"search results page", re.IGNORECASE),
    re.compile(r"webcache\.googleusercontent\.com", re.IGNORECASE),
]

# Anti-bot / JS-required interstitials served to non-browser clients (httpx has no JS engine).
BOT_CHALLENGE_PATTERNS = [
    re.compile(r"javascript is disabled", re.IGNORECASE),
    re.compile(r"please enable javascript", re.IGNORECASE),
    re.compile(r"enable javascript to proceed", re.IGNORECASE),
    re.compile(r"a required part of this site couldn'?t load", re.IGNORECASE),
    re.compile(r"disable any ad blockers", re.IGNORECASE),
    re.compile(r"may be due to a browser extension", re.IGNORECASE),
    re.compile(r"checking your browser", re.IGNORECASE),
    re.compile(r"just a moment", re.IGNORECASE),
    re.compile(r"attention required", re.IGNORECASE),
    re.compile(r"unusual traffic from your computer network", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"request blocked", re.IGNORECASE),
]

STRIP_TAGS = {
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    "form",
    "nav",
    "footer",
    "aside",
    "dialog",
    "button",
}


# Unambiguous challenge boilerplate used for *paragraph-level* stripping. Generic
# phrases ("just a moment", "access denied", "attention required", "request
# blocked") stay in BOT_CHALLENGE_PATTERNS for whole-page checks only, so a short
# legitimate sentence in a real article is never removed.
CHALLENGE_PARAGRAPH_PATTERNS = [
    re.compile(r"javascript is disabled", re.IGNORECASE),
    re.compile(r"please enable javascript", re.IGNORECASE),
    re.compile(r"enable javascript to proceed", re.IGNORECASE),
    re.compile(r"a required part of this site couldn'?t load", re.IGNORECASE),
    re.compile(r"disable any ad blockers", re.IGNORECASE),
    re.compile(r"may be due to a browser extension", re.IGNORECASE),
]


def _is_boilerplate_paragraph(text: str, limit: int = 140) -> bool:
    """Short paragraphs matching paywall/unambiguous anti-bot boilerplate are chrome, not content."""
    if len(text) >= limit:
        return False
    if any(rx.search(text) for rx in PAYWALL_BOILERPLATE_PATTERNS):
        return True
    return any(rx.search(text) for rx in CHALLENGE_PARAGRAPH_PATTERNS)


def safe_hostname(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        return re.sub(r"^www\.", "", host.lower()) or None
    except Exception:
        return None


def build_exact_offset_passages(
    text_content: str,
    chapter_title: Optional[str] = None,
    page_or_timestamp_map: Optional[Dict[int, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Splits clean text_content into indexed paragraphs while recording exact
    start_char and end_char offsets so text_content[start_char:end_char] == text
    is strictly preserved for verifiable RAG citations.
    """
    full_text = text_content or ""
    if not full_text.strip():
        return []

    raw_blocks = re.split(r"\n\s*\n", full_text)
    passages: List[Dict[str, Any]] = []
    cursor = 0
    para_idx = 0

    for block in raw_blocks:
        trimmed = block.strip()
        if not trimmed:
            continue
        found_at = full_text.find(trimmed, cursor)
        start_char = found_at if found_at >= 0 else cursor
        end_char = start_char + len(trimmed)
        cursor = end_char

        passages.append(
            {
                "paragraph_index": para_idx,
                "chapter_title": chapter_title,
                "page_or_timestamp": (page_or_timestamp_map or {}).get(para_idx),
                "start_char": start_char,
                "end_char": end_char,
                "text": trimmed,
            }
        )
        para_idx += 1

    return passages


def format_copy_to_llm_markdown(
    *,
    title: str,
    url: str = "",
    author: Optional[str] = None,
    site_name: Optional[str] = None,
    published_time: Optional[str] = None,
    source_used: str = "direct",
    word_count: int = 0,
    reading_time_minutes: int = 1,
    markdown_body: str = "",
    include_prompt_header: bool = True,
) -> str:
    """
    One-Click 'Copy to LLMs' utility: formats the stripped article/book/transcript
    into clean, structured Markdown ready for ChatGPT, Claude, Gemini, OpenRouter, or Ollama.
    """
    lines: List[str] = []
    if include_prompt_header:
        lines.extend(
            [
                "Below is the full, distraction-free source text extracted via Summary AI.",
                "Use this primary source to summarize, analyze, or answer questions with exact quotes.",
                "",
                "---",
                "",
            ]
        )

    lines.append(f"# {title or 'Untitled Document'}")
    lines.append("")

    meta: List[str] = []
    if url:
        meta.append(f"- **Source URL:** {url}")
    if site_name:
        meta.append(f"- **Publication:** {site_name}")
    if author:
        meta.append(f"- **Author:** {author}")
    if published_time:
        meta.append(f"- **Published:** {published_time}")
    if source_used:
        meta.append(f"- **Extracted Via:** `{source_used}`")
    meta.append(f"- **Reading Time:** ~{reading_time_minutes} min ({word_count} words)")

    lines.extend(meta)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append((markdown_body or "").strip())
    return "\n".join(lines).strip()


def _extract_meta(soup: BeautifulSoup, attr_name: str, attr_val: str) -> Optional[str]:
    tag = soup.find("meta", attrs={attr_name: re.compile(f"^{re.escape(attr_val)}$", re.I)})
    if tag and isinstance(tag, Tag):
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return html_lib.unescape(content.strip())
    return None


def sanitize_and_extract_html(
    raw_html: str,
    url: str = "",
    source_used: str = "direct",
) -> Dict[str, Any]:
    """
    Multi-stage Distraction-Free Reader & Soft-Paywall Stripper:
    1. Extracts metadata (title, author, site_name, published_time, canonical_url).
    2. Strips scripts, styles, iframes, popups, ads, cookie banners, newsletter modals,
       and soft paywall overlays.
    3. Extracts clean Reader HTML, structured Markdown, plain text, and exact-offset passages.
    """
    html_text = str(raw_html or "")
    raw_paywall_hit = any(rx.search(html_text) for rx in PAYWALL_BOILERPLATE_PATTERNS)
    raw_redirect_hit = (
        any(rx.search(html_text) for rx in REDIRECT_INTERSTITIAL_PATTERNS)
        or any(rx.search(html_text) for rx in BOT_CHALLENGE_PATTERNS)
    )

    soup = BeautifulSoup(html_text, "lxml")

    # 1. Extract metadata before mutating DOM
    og_title = _extract_meta(soup, "property", "og:title")
    tw_title = _extract_meta(soup, "name", "twitter:title")
    h1_tag = soup.find("h1")
    title_tag = soup.find("title")

    raw_title = (
        og_title
        or tw_title
        or (h1_tag.get_text(" ", strip=True) if h1_tag else None)
        or (title_tag.get_text(" ", strip=True) if title_tag else None)
        or url
        or "Untitled Article"
    )
    title = re.sub(r"\s+", " ", html_lib.unescape(raw_title)).strip()

    author = (
        _extract_meta(soup, "name", "author")
        or _extract_meta(soup, "property", "article:author")
        or _extract_meta(soup, "name", "byl")
    )
    site_name = _extract_meta(soup, "property", "og:site_name") or safe_hostname(url)
    published_time = (
        _extract_meta(soup, "property", "article:published_time")
        or _extract_meta(soup, "name", "pubdate")
        or _extract_meta(soup, "name", "date")
    )
    description = (
        _extract_meta(soup, "property", "og:description")
        or _extract_meta(soup, "name", "description")
    )
    canonical_link = soup.find("link", rel=lambda v: v and "canonical" in str(v).lower())
    canonical_url = (
        canonical_link.get("href")
        if isinstance(canonical_link, Tag) and isinstance(canonical_link.get("href"), str)
        else url or None
    )

    # og:image / twitter:image for library card thumbnails. Relative URLs are
    # resolved against the page URL; only absolute http(s) URLs <= 2048 chars
    # are kept.
    image_url = None
    image_candidate = (
        _extract_meta(soup, "property", "og:image")
        or _extract_meta(soup, "name", "twitter:image")
        or _extract_meta(soup, "name", "twitter:image:src")
    )
    if image_candidate:
        try:
            resolved = urljoin(url or "", image_candidate.strip())
            if (
                urlparse(resolved).scheme in ("http", "https")
                and len(resolved) <= 2048
            ):
                image_url = resolved
        except ValueError:
            pass  # Malformed optional image metadata must not abort extraction.

    stripped_count = 0

    # 2. Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 3. Strip unwanted tags (<script>, <style>, <iframe>, <nav>, <footer>, <aside>, etc.)
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()
        stripped_count += 1

    # 4. Strip popups, ads, cookie banners, newsletter modals, and soft paywall overlays
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag) or tag.attrs is None:
            continue
        if tag.name in ("html", "body", "article", "main"):
            # Un-blur or unlock soft-paywalled article/body containers
            if tag.has_attr("style"):
                del tag["style"]
            continue

        # Strip <header> elements that look like site navigation chrome (not article headers)
        if tag.name == "header":
            classes = " ".join(tag.get("class", [])) if isinstance(tag.get("class"), list) else str(tag.get("class", ""))
            el_id = str(tag.get("id", ""))
            combined_attr = f"{classes} {el_id}".lower()
            if DISTRACTION_KEYWORDS_RE.search(combined_attr) or any(
                k in combined_attr for k in ("global-nav", "main-nav", "site-nav", "utility-nav", "header-nav")
            ):
                tag.decompose()
                stripped_count += 1
                continue

        classes = " ".join(tag.get("class", [])) if isinstance(tag.get("class"), list) else str(tag.get("class", ""))
        el_id = str(tag.get("id", ""))
        role = str(tag.get("role", ""))
        combined_attr = f"{classes} {el_id} {role}"

        if DISTRACTION_KEYWORDS_RE.search(combined_attr):
            tag.decompose()
            stripped_count += 1

    # 4b. Strip remaining chrome sections whose visible text indicates non-article chrome
    # (e.g., "More Stories From NPR", "Popular on NPR.org", "Editors' Picks", cookie modals)
    CHROME_HEADING_RE = re.compile(
        r"\b(more stories|popular on|editors' picks|editors picks|cookie settings|"
        r"consent legs|become an npr sponsor|get npr\+|npr does not offer|"
        r"terms of use|privacy policy|text only|accessibility links|"
        r"keyboard shortcuts|skip to main|donate|npr shop|newsletters|"
        r"sign in|personalize your experience|about npr|public editor|corrections|"
        r"transcripts|contact & help|support public radio|sponsor npr|npr careers|"
        r"npr extra|diversity|network|finances)\b",
        re.IGNORECASE,
    )
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag) or tag.attrs is None:
            continue
        if tag.name in ("html", "body", "article", "main", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre"):
            continue
        # Never strip chrome-heading matches nested inside article content —
        # only standalone blocks outside <article>/<main> are chrome.
        if tag.find_parent(["article", "main"]):
            continue
        text_val = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
        if not text_val:
            continue
        # Only strip standalone chrome blocks (not inline within article paragraphs)
        if CHROME_HEADING_RE.match(text_val[:120]) and len(text_val) < 200:
            tag.decompose()
            stripped_count += 1

    # 5. Select primary content container (<article>, <main>, or Readability fallback)
    scope: Tag | BeautifulSoup = soup
    article_el = soup.find("article")
    main_el = soup.find("main")

    if isinstance(article_el, Tag) and len(article_el.get_text(" ", strip=True)) > 120:
        scope = article_el
    elif isinstance(main_el, Tag) and len(main_el.get_text(" ", strip=True)) > 120:
        scope = main_el
    else:
        body_el = soup.find("body")
        if isinstance(body_el, Tag):
            scope = body_el

    # 6. Extract clean structured blocks
    clean_html_blocks: List[str] = []
    markdown_blocks: List[str] = []
    text_paragraphs: List[str] = []

    content_tags = scope.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"])
    seen_texts: set[str] = set()

    for node in content_tags:
        if not isinstance(node, Tag):
            continue
        text_val = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if not text_val:
            continue
        # Skip short paywall/cookie/anti-bot boilerplate paragraphs
        if _is_boilerplate_paragraph(text_val):
            stripped_count += 1
            continue
        # Avoid duplicate nested captures
        if node.name == "li" and node.find_parent("li") is not None:
            continue
        if text_val in seen_texts and len(text_val) < 80:
            continue
        seen_texts.add(text_val)

        escaped_html = html_lib.escape(text_val)
        tag_name = node.name.lower()

        if tag_name.startswith("h"):
            level = int(tag_name[1]) if len(tag_name) > 1 and tag_name[1].isdigit() else 2
            if text_val.lower() == title.lower() and level == 1:
                continue
            hashes = "#" * min(max(level, 1), 6)
            clean_html_blocks.append(f"<{tag_name}>{escaped_html}</{tag_name}>")
            markdown_blocks.append(f"{hashes} {text_val}")
            text_paragraphs.append(text_val)
        elif tag_name == "li":
            clean_html_blocks.append(f'<p class="reader-list-item">• {escaped_html}</p>')
            markdown_blocks.append(f"- {text_val}")
            text_paragraphs.append(f"• {text_val}")
        elif tag_name == "blockquote":
            clean_html_blocks.append(f"<blockquote>{escaped_html}</blockquote>")
            markdown_blocks.append(f"> {text_val}")
            text_paragraphs.append(text_val)
        elif tag_name == "pre":
            clean_html_blocks.append(f"<pre><code>{escaped_html}</code></pre>")
            markdown_blocks.append(f"```\n{text_val}\n```")
            text_paragraphs.append(text_val)
        else:
            clean_html_blocks.append(f"<p>{escaped_html}</p>")
            markdown_blocks.append(text_val)
            text_paragraphs.append(text_val)

    # 7. Fallback to trafilatura or plain text splitting if no standard block tags matched
    if not text_paragraphs:
        traf_text = trafilatura.extract(html_text, include_comments=False, include_tables=True) or ""
        if not traf_text.strip():
            try:
                readability_doc = ReadabilityDocument(html_text)
                traf_text = BeautifulSoup(readability_doc.summary(), "lxml").get_text("\n\n", strip=True)
            except Exception:
                traf_text = scope.get_text("\n\n", strip=True)

        for raw_para in re.split(r"\n\s*\n", traf_text):
            cleaned = re.sub(r"\s+", " ", raw_para).strip()
            if not cleaned:
                continue
            if _is_boilerplate_paragraph(cleaned):
                stripped_count += 1
                continue
            clean_html_blocks.append(f"<p>{html_lib.escape(cleaned)}</p>")
            markdown_blocks.append(cleaned)
            text_paragraphs.append(cleaned)

    text_content = "\n\n".join(text_paragraphs).strip()
    content_html = "\n".join(clean_html_blocks).strip()
    markdown_body = "\n\n".join(markdown_blocks).strip()

    words = text_content.split() if text_content else []
    word_count = len(words)
    reading_time_minutes = max(1, (word_count + 219) // 220)
    excerpt = description or (text_paragraphs[0][:260] if text_paragraphs else "")
    paywall_detected = bool(raw_paywall_hit and word_count < 100)

    passages = build_exact_offset_passages(text_content)
    llm_markdown = format_copy_to_llm_markdown(
        title=title,
        url=url,
        author=author,
        site_name=site_name,
        published_time=published_time,
        source_used=source_used,
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
        markdown_body=markdown_body,
    )

    return {
        "url": url,
        "canonical_url": canonical_url,
        "image_url": image_url,
        "title": title,
        "author": author,
        "site_name": site_name,
        "published_time": published_time,
        "media_type": "article",
        "excerpt": excerpt,
        "content_html": content_html,
        "text_content": text_content,
        "markdown": markdown_body,
        "llm_markdown": llm_markdown,
        "word_count": word_count,
        "reading_time_minutes": reading_time_minutes,
        "stripped_elements_count": stripped_count,
        "paywall_detected": paywall_detected,
        "redirect_detected": bool(raw_redirect_hit and word_count < 100),
        "source_used": source_used,
        "passages": passages,
    }
