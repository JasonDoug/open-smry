"""
Dense Vector Embedding Engine for Summary AI.
Supports:
1. Local AI (Ollama /api/embed with nomic-embed-text or nomic-embed-text-v2-moe)
2. Deterministic 256-dim L2-normalized Semantic Feature-Hashing Embeddings (NumPy)
   for zero-latency offline & CI hybrid retrieval.
"""
from __future__ import annotations

import hashlib
import re
from typing import List, Optional

import httpx
import numpy as np

from app.config import get_settings

EMBEDDING_DIM = 256

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "what", "when", "where",
    "which", "who", "whom", "whose", "why", "how", "are", "was", "were", "been",
    "being", "have", "has", "had", "does", "did", "will", "would", "should",
    "could", "can", "may", "might", "must", "shall", "into", "onto", "upon",
    "about", "above", "below", "between", "through", "during", "before", "after",
    "over", "under", "again", "further", "then", "once", "here", "there",
}


def tokenize_text(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]{2,}", (text or "").lower())
    return [t for t in tokens if t not in STOPWORDS]


def compute_deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Computes a 256-dimensional L2-normalized semantic projection using token unigrams,
    token bigrams, and character 4-grams with signed Murmur/MD5 feature hashing.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = tokenize_text(text)
    if not tokens:
        return vec.tolist()

    features: List[tuple[str, float]] = []
    # Token unigrams (weight 2.0)
    for tok in tokens:
        features.append((f"u:{tok}", 2.0))
        # Character prefixes/stems for morphological invariance (weight 1.0)
        if len(tok) >= 5:
            features.append((f"s:{tok[:5]}", 1.0))

    # Token bigrams (weight 1.5)
    for i in range(len(tokens) - 1):
        features.append((f"b:{tokens[i]}_{tokens[i + 1]}", 1.5))

    for feat, weight in features:
        digest = hashlib.md5(feat.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign * weight

    norm = float(np.linalg.norm(vec))
    if norm > 1e-8:
        vec = vec / norm

    return [round(float(x), 6) for x in vec]


async def compute_ollama_embedding(
    text: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Optional[List[float]]:
    """
    Queries Local Ollama (/api/embed) for dense embeddings if requested and reachable.
    """
    settings = get_settings()
    target_url = (base_url or settings.ollama_base_url).rstrip("/") + "/api/embed"
    target_model = model or settings.ollama_embedding_model

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=3.0)
    try:
        resp = await client.post(
            target_url,
            json={"model": target_model, "input": text},
        )
        if resp.status_code == 200:
            data = resp.json()
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
                raw_vec = np.array(embeddings[0], dtype=np.float32)
                norm = float(np.linalg.norm(raw_vec))
                if norm > 1e-8:
                    raw_vec = raw_vec / norm
                return [round(float(x), 6) for x in raw_vec]
    except Exception:
        return None
    finally:
        if owns_client:
            await client.aclose()
    return None


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-8:
        return 0.0
    return float(np.dot(a, b) / denom)
