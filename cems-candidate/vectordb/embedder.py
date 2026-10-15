"""
vectordb/embedder.py — local embeddings via Ollama (nomic-embed-text, 768-dim).
No API cost, no rate limits — unlike the OpenRouter classification calls.

The ollama package is imported lazily: modules that import this one (RAG, recommender, ingest)
still import when ollama is not installed or not running; the failure surfaces as an exception
from embed_text(), which callers already treat as "embeddings unavailable".
"""
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

_client = None


def _get_client():
    global _client
    if _client is None:
        import ollama  # lazy: see module docstring
        _client = ollama.Client(host=OLLAMA_HOST)
    return _client


def embed_text(text: str) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")
    response = _get_client().embeddings(model=EMBED_MODEL, prompt=text)
    vector = list(response["embedding"])
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"{EMBED_MODEL} returned {len(vector)} dims, expected {EMBEDDING_DIM}")
    return vector


def embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """One vector per text, or None where embedding failed. (It used to return an all-zero
    vector on failure; such a point is meaningless for cosine search and pollutes Qdrant.)"""
    vectors: List[Optional[List[float]]] = []
    for t in texts:
        try:
            vectors.append(embed_text(t))
        except Exception as e:
            logger.warning(f"Embedding failed (len={len(t or '')}): {e}")
            vectors.append(None)
    return vectors


def _model_names(listing) -> set:
    """ollama.list() returns a dict with 'name' keys in old clients and objects with a .model
    attribute in newer ones; the old code only read ['name'] and reported 'not ready'."""
    models = listing["models"] if isinstance(listing, dict) else getattr(listing, "models", [])
    names = set()
    for m in models:
        for key in ("name", "model"):
            v = m.get(key) if isinstance(m, dict) else getattr(m, key, None)
            if v:
                names.add(str(v))
    return names


def check_ready() -> bool:
    try:
        available = _model_names(_get_client().list())
    except Exception as e:
        logger.error(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}")
        return False
    base = EMBED_MODEL.split(":")[0]
    if not any(m == EMBED_MODEL or m.split(":")[0] == base for m in available):
        logger.error(f"Missing model {EMBED_MODEL} — run: ollama pull {EMBED_MODEL}")
        return False
    return True
