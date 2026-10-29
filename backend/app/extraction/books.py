"""
Book & Long-Form Document Ingestion Engine (PDF, EPUB, Markdown/Text).
Extracts chapters, page numbers, clean Reader HTML, Copy-to-LLM Markdown,
and exact character-offset passages so books get read, summarized, and filed.
"""
from __future__ import annotations

import html as html_lib
import io
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
import pymupdf

from app.extraction.sanitizer import (
    build_exact_offset_passages,
    format_copy_to_llm_markdown,
)


def parse_pdf_bytes(
    pdf_bytes: bytes,
    *,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    source_url: str = "book://pdf-upload",
) -> Dict[str, Any]:
    """
    Extracts pages and paragraphs from a PDF book or research paper using PyMuPDF,
    preserving exact character offsets and page citations ('Page N').
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    meta = doc.metadata or {}
    title = title_override or (meta.get("title") or "").strip() or "Uploaded PDF Book"
    author = author_override or (meta.get("author") or "").strip() or None

    html_blocks: List[str] = []
    md_blocks: List[str] = []
    text_paragraphs: List[str] = []
    page_map: Dict[int, str] = {}

    for page_idx in range(len(doc)):
        page = doc.load_page(page_idx)
        page_num = page_idx + 1
        raw_page_text = page.get_text("text") or ""
        paras = [
            re.sub(r"\s+", " ", p).strip()
            for p in re.split(r"\n\s*\n", raw_page_text)
            if p.strip()
        ]
        if not paras:
            continue

        html_blocks.append(f'<h3 class="book-page-heading">Page {page_num}</h3>')
        md_blocks.append(f"### Page {page_num}")

        for p in paras:
            para_idx = len(text_paragraphs)
            page_map[para_idx] = f"Page {page_num}"
            html_blocks.append(f"<p>{html_lib.escape(p)}</p>")
            md_blocks.append(p)
            text_paragraphs.append(p)

    doc.close()

    text_content = "\n\n".join(text_paragraphs).strip()
    content_html = "\n".join(html_blocks).strip()
    markdown_body = "\n\n".join(md_blocks).strip()
    word_count = len(text_content.split()) if text_content else 0
    reading_time_minutes = max(1, (word_count + 219) // 220)

    passages = build_exact_offset_passages(
        text_content,
        chapter_title=title,
        page_or_timestamp_map=page_map,
    )
    llm_markdown = format_copy_to_llm_markdown(
        title=title,
        url=source_url,
        author=author,
        site_name="PDF Book / Document",
        source_used="pdf-parser",
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
        markdown_body=markdown_body,
    )

    return {
        "url": source_url,
        "canonical_url": source_url,
        "title": title,
        "author": author,
        "site_name": "PDF Book",
        "published_time": None,
        "media_type": "book",
        "excerpt": text_paragraphs[0][:260] if text_paragraphs else "",
        "content_html": content_html,
        "text_content": text_content,
        "markdown": markdown_body,
        "llm_markdown": llm_markdown,
        "word_count": word_count,
        "reading_time_minutes": reading_time_minutes,
        "stripped_elements_count": 0,
        "paywall_detected": False,
        "source_used": "pdf-parser",
        "source_score": 100.0,
        "source_attempts": [
            {
                "source": "pdf-parser",
                "status": "ok",
                "word_count": word_count,
                "score": 100.0,
                "latency_ms": 5,
                "selected": True,
            }
        ],
        "passages": passages,
    }


def parse_epub_bytes(
    epub_bytes: bytes,
    *,
    title_override: Optional[str] = None,
    author_override: Optional[str] = None,
    source_url: str = "book://epub-upload",
) -> Dict[str, Any]:
    """
    Extracts chapters and paragraphs from an EPUB book using ebooklib + BeautifulSoup.
    """
    book = epub.read_epub(io.BytesIO(epub_bytes))
    dc_titles = book.get_metadata("DC", "title")
    dc_creators = book.get_metadata("DC", "creator")

    title = title_override or (dc_titles[0][0] if dc_titles else "Uploaded EPUB Book")
    author = author_override or (dc_creators[0][0] if dc_creators else None)

    html_blocks: List[str] = []
    md_blocks: List[str] = []
    text_paragraphs: List[str] = []
    chapter_map: Dict[int, str] = {}
    chapter_num = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        heading = soup.find(["h1", "h2", "h3"])
        chapter_num += 1
        chapter_name = (
            heading.get_text(" ", strip=True)
            if heading
            else f"Chapter {chapter_num}"
        )

        paras = [
            re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
            for p in soup.find_all(["p", "blockquote", "li"])
        ]
        paras = [p for p in paras if p]
        if not paras:
            continue

        html_blocks.append(f"<h2>{html_lib.escape(chapter_name)}</h2>")
        md_blocks.append(f"## {chapter_name}")

        for p in paras:
            para_idx = len(text_paragraphs)
            chapter_map[para_idx] = chapter_name
            html_blocks.append(f"<p>{html_lib.escape(p)}</p>")
            md_blocks.append(p)
            text_paragraphs.append(p)

    text_content = "\n\n".join(text_paragraphs).strip()
    content_html = "\n".join(html_blocks).strip()
    markdown_body = "\n\n".join(md_blocks).strip()
    word_count = len(text_content.split()) if text_content else 0
    reading_time_minutes = max(1, (word_count + 219) // 220)

    passages = build_exact_offset_passages(
        text_content,
        chapter_title=title,
        page_or_timestamp_map=chapter_map,
    )
    llm_markdown = format_copy_to_llm_markdown(
        title=title,
        url=source_url,
        author=author,
        site_name="EPUB Book",
        source_used="epub-parser",
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
        markdown_body=markdown_body,
    )

    return {
        "url": source_url,
        "canonical_url": source_url,
        "title": title,
        "author": author,
        "site_name": "EPUB Book",
        "published_time": None,
        "media_type": "book",
        "excerpt": text_paragraphs[0][:260] if text_paragraphs else "",
        "content_html": content_html,
        "text_content": text_content,
        "markdown": markdown_body,
        "llm_markdown": llm_markdown,
        "word_count": word_count,
        "reading_time_minutes": reading_time_minutes,
        "stripped_elements_count": 0,
        "paywall_detected": False,
        "source_used": "epub-parser",
        "source_score": 100.0,
        "source_attempts": [
            {
                "source": "epub-parser",
                "status": "ok",
                "word_count": word_count,
                "score": 100.0,
                "latency_ms": 8,
                "selected": True,
            }
        ],
        "passages": passages,
    }


def parse_text_or_markdown_book(
    text_content_raw: str,
    *,
    title: str = "Submitted Book / Document",
    author: Optional[str] = None,
    source_url: str = "book://markdown-document",
) -> Dict[str, Any]:
    """
    Parses Markdown or plain-text books/chapters into structured paragraphs and exact-offset passages.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text_content_raw or "") if b.strip()]
    html_blocks: List[str] = []
    md_blocks: List[str] = []
    text_paragraphs: List[str] = []
    chapter_map: Dict[int, str] = {}
    current_chapter = "Chapter 1"

    for b in blocks:
        if b.startswith("#"):
            clean_heading = re.sub(r"^#+\s*", "", b).strip()
            current_chapter = clean_heading or current_chapter
            html_blocks.append(f"<h2>{html_lib.escape(clean_heading)}</h2>")
            md_blocks.append(f"## {clean_heading}")
            continue

        clean_para = re.sub(r"\s+", " ", b).strip()
        para_idx = len(text_paragraphs)
        chapter_map[para_idx] = current_chapter
        html_blocks.append(f"<p>{html_lib.escape(clean_para)}</p>")
        md_blocks.append(clean_para)
        text_paragraphs.append(clean_para)

    text_content = "\n\n".join(text_paragraphs).strip()
    content_html = "\n".join(html_blocks).strip()
    markdown_body = "\n\n".join(md_blocks).strip()
    word_count = len(text_content.split()) if text_content else 0
    reading_time_minutes = max(1, (word_count + 219) // 220)

    passages = build_exact_offset_passages(
        text_content,
        chapter_title=title,
        page_or_timestamp_map=chapter_map,
    )
    llm_markdown = format_copy_to_llm_markdown(
        title=title,
        url=source_url,
        author=author,
        site_name="Book / Long-Form Document",
        source_used="book-markdown",
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
        markdown_body=markdown_body,
    )

    return {
        "url": source_url,
        "canonical_url": source_url,
        "title": title,
        "author": author,
        "site_name": "Book / Document",
        "published_time": None,
        "media_type": "book",
        "excerpt": text_paragraphs[0][:260] if text_paragraphs else "",
        "content_html": content_html,
        "text_content": text_content,
        "markdown": markdown_body,
        "llm_markdown": llm_markdown,
        "word_count": word_count,
        "reading_time_minutes": reading_time_minutes,
        "stripped_elements_count": 0,
        "paywall_detected": False,
        "source_used": "book-markdown",
        "source_score": 100.0,
        "source_attempts": [
            {
                "source": "book-markdown",
                "status": "ok",
                "word_count": word_count,
                "score": 100.0,
                "latency_ms": 1,
                "selected": True,
            }
        ],
        "passages": passages,
    }
