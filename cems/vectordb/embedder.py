"""
vectordb/embedder.py — local embeddings via Ollama (nomic-embed-text, 768-dim).
No API cost, no rate limits — unlike the OpenRouter classification calls.
"""
import os
import logging
from typing import List

import ollama

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

_client = ollama.Client(host=OLLAMA_HOST)


def embed_text(text: str) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")
    response = _client.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def embed_batch(texts: List[str]) -> List[List[float]]:
    vectors = []
    for t in texts:
        try:
            vectors.append(embed_text(t))
        except Exception as e:
            logger.warning(f"Embedding failed (len={len(t)}): {e}")
            vectors.append([0.0] * 768)
    return vectors


def check_ready() -> bool:
    try:
        available = {m["name"] for m in _client.list()["models"]}
    except Exception as e:
        logger.error(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}")
        return False
    if not any(m == EMBED_MODEL or m.startswith(EMBED_MODEL.split(":")[0]) for m in available):
        logger.error(f"Missing model {EMBED_MODEL} — run: ollama pull {EMBED_MODEL}")
        return False
    return True
