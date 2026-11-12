"""
Reader-mode cleanup of academic markup (BUG-031):
- Screen-reader-only helper text ("Footnote ", "Reference ...") is removed.
- In-text footnote markers (<a href="#fn2"><sup>1</sup></a>) are removed.
- Bibliography links keep their visible citation text (author/year).
- Stray spaces introduced at inline-tag boundaries are tidied.
"""
from __future__ import annotations

from app.extraction.sanitizer import sanitize_and_extract_html, tidy_inline_spacing

ARTICLE = """<html><head><meta property="og:title" content="Hoc Saxsum : History"></head><body><article>
<p>Rome’s first written histories.<a class="xref fn" href="#fn2"><span class="show-for-sr">Footnote </span><sup class="sup">1</sup></a> The temporal proximity is clear.</p>
<p>See Badian <a class="xref bibr" href="#ref3"><span class="show-for-sr">Reference Badian and Dorey</span>1966</a>: 1–38, dating to the third century <em>b.c.e</em>. ( <em>Photograph: Author</em> )</p>
<p>The ’90s revival and a <a href="#section-2">linked section</a> remain intact.</p>
</article></body></html>"""


def test_footnote_markers_and_sr_only_text_removed() -> None:
    """Footnote markers and screen-reader-only labels never reach reader text."""
    text = sanitize_and_extract_html(ARTICLE, url="https://example.org/a")["text_content"]
    assert "Footnote" not in text
    assert "Reference" not in text
    assert "histories. The temporal proximity" in text


def test_bibliography_years_and_prose_links_kept() -> None:
    """Citation years and ordinary in-page links survive marker stripping."""
    text = sanitize_and_extract_html(ARTICLE, url="https://example.org/a")["text_content"]
    assert "Badian 1966: 1–38" in text
    assert "linked section" in text
    assert "’90s" in text


def test_inline_spacing_artifacts_tidied() -> None:
    """Spaces before punctuation / inside parentheses from tag boundaries are removed."""
    doc = sanitize_and_extract_html(ARTICLE, url="https://example.org/a")
    assert "century b.c.e. (Photograph: Author)" in doc["text_content"]
    assert doc["title"] == "Hoc Saxsum: History"
    assert tidy_inline_spacing("a ( b ) , c ; d ” e") == "a (b), c; d” e"
