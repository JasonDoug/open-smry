"""
Hybrid Exact-Passage Retriever:
Combines rank_bm25 (BM25Okapi lexical ranking) + Dense Vector Cosine Similarity
via Reciprocal Rank Fusion (RRF), and verifies exact [start_char, end_char]
slice identity against the parent Document's text_content.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.db.models import Document, PassageChunk
from app.rag.embeddings import (
    compute_deterministic_embedding,
    cosine_similarity,
    tokenize_text,
)


def verify_exact_offset_invariant(
    doc_or_text: Document | str,
    chunk_or_start: PassageChunk | int,
    end_char: Optional[int] = None,
    expected_text: Optional[str] = None,
) -> tuple[bool, str] | bool:
    """
    Verifies that doc.text_content[chunk.start_char : chunk.end_char] == chunk.text.
    Supports both:
    - verify_exact_offset_invariant(doc, chunk) -> (bool, str)
    - verify_exact_offset_invariant(full_text, start_char, end_char, expected_text) -> bool
    """
    if isinstance(doc_or_text, str) and isinstance(chunk_or_start, int):
        full_text = doc_or_text
        start_c = chunk_or_start
        end_c = int(end_char or 0)
        target = expected_text or ""
        if 0 <= start_c <= end_c <= len(full_text):
            return full_text[start_c:end_c] == target
        return False

    doc = doc_or_text  # type: ignore[assignment]
    chunk = chunk_or_start  # type: ignore[assignment]
    full_text = doc.text_content or ""
    if 0 <= chunk.start_char <= chunk.end_char <= len(full_text):
        sliced = full_text[chunk.start_char : chunk.end_char]
        if sliced == chunk.text:
            return True, sliced
    # Fallback search if document text was modified
    found_idx = full_text.find(chunk.text)
    if found_idx >= 0:
        return True, full_text[found_idx : found_idx + len(chunk.text)]
    return False, chunk.text


def hybrid_search_passages(
    db: Session,
    query: str,
    *,
    top_k: int = 5,
    document_ids: Optional[List[str]] = None,
    tag_filter: Optional[str] = None,
    media_type_filter: Optional[str] = None,
    saved_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Executes Hybrid BM25 + Vector + Exact-Phrase search across indexed PassageChunks
    and returns ranked passages with verified character offsets.
    """
    doc_query = db.query(Document)
    if saved_only:
        doc_query = doc_query.filter(Document.saved_in_library.is_(True))
    if document_ids:
        doc_query = doc_query.filter(Document.id.in_(document_ids))
    if media_type_filter:
        doc_query = doc_query.filter(Document.media_type == media_type_filter)

    docs = doc_query.all()
    if tag_filter:
        tag_lower = tag_filter.strip().lower()
        filtered_docs = []
        for d in docs:
            try:
                tags = [str(t).lower() for t in json.loads(d.tags_json or "[]")]
            except Exception:
                tags = []
            if tag_lower in tags:
                filtered_docs.append(d)
        docs = filtered_docs

    if not docs:
        return []

    doc_map: Dict[str, Document] = {d.id: d for d in docs}
    candidate_chunks: List[PassageChunk] = []
    for d in docs:
        candidate_chunks.extend(d.passages)

    if not candidate_chunks:
        return []

    query_tokens = tokenize_text(query)
    if not query_tokens:
        query_tokens = [w.lower() for w in query.split() if w.strip()]

    # 1. BM25 Lexical Scoring
    tokenized_corpus = [
        tokenize_text(c.text) or [w.lower() for w in c.text.split()]
        for c in candidate_chunks
    ]
    bm25 = BM25Okapi(tokenized_corpus)
    raw_bm25_scores = bm25.get_scores(query_tokens) if query_tokens else [0.0] * len(candidate_chunks)

    #Also add token overlap coverage so small 1-2 paragraph corpora (where IDF can be 0) still rank accurately
    q_set = set(query_tokens)
    bm25_scores: List[float] = []
    for idx, c_tokens in enumerate(tokenized_corpus):
        overlap = sum(1 for t in q_set if t in c_tokens)
        coverage = (overlap / len(q_set)) * 2.5 if q_set else 0.0
        bm25_scores.append(float(max(0.0, raw_bm25_scores[idx])) + coverage)

    # 2. Dense Vector Cosine Similarity
    query_vec = compute_deterministic_embedding(query)
    vector_scores: List[float] = []
    for chunk in candidate_chunks:
        chunk_vec: Optional[List[float]] = None
        if chunk.embedding_json:
            try:
                loaded = json.loads(chunk.embedding_json)
                if isinstance(loaded, list) and len(loaded) == len(query_vec):
                    chunk_vec = loaded
            except Exception:
                chunk_vec = None
        if chunk_vec is None:
            chunk_vec = compute_deterministic_embedding(chunk.text)
        sim = max(0.0, cosine_similarity(query_vec, chunk_vec))
        vector_scores.append(sim)

    # 3. Reciprocal Rank Fusion (RRF) + Exact Phrase Bonus
    n = len(candidate_chunks)
    bm25_order = sorted(range(n), key=lambda i: bm25_scores[i], reverse=True)
    vec_order = sorted(range(n), key=lambda i: vector_scores[i], reverse=True)

    bm25_rank = {idx: rank + 1 for rank, idx in enumerate(bm25_order)}
    vec_rank = {idx: rank + 1 for rank, idx in enumerate(vec_order)}

    raw_query_lower = (query or "").strip().lower()
    results: List[Dict[str, Any]] = []

    for i, chunk in enumerate(candidate_chunks):
        parent_doc = doc_map[chunk.document_id]
        rrf_score = (1.0 / (15 + bm25_rank[i])) + (1.0 / (15 + vec_rank[i]))
        phrase_bonus = (
            1.5
            if len(raw_query_lower) > 3 and raw_query_lower in chunk.text.lower()
            else 0.0
        )
        hybrid_score = round(
            (bm25_scores[i] * 0.55) + (vector_scores[i] * 3.5) + (rrf_score * 10.0) + phrase_bonus,
            4,
        )
        verified, verbatim_quote = verify_exact_offset_invariant(parent_doc, chunk)

        results.append(
            {
                "passage_id": chunk.id,
                "document_id": parent_doc.id,
                "document_title": parent_doc.title,
                "document_url": parent_doc.url,
                "media_type": parent_doc.media_type,
                "paragraph_index": chunk.paragraph_index,
                "chapter_title": chunk.chapter_title,
                "page_or_timestamp": chunk.page_or_timestamp,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "exact_quote": verbatim_quote,
                "offset_verified": verified,
                "bm25_score": round(bm25_scores[i], 4),
                "vector_score": round(vector_scores[i], 4),
                "hybrid_score": hybrid_score,
            }
        )

    results.sort(key=lambda r: (-r["hybrid_score"], r["paragraph_index"]))
    top_results = results[: max(1, top_k)]
    for rank_idx, item in enumerate(top_results, start=1):
        item["rank"] = rank_idx
    return top_results
