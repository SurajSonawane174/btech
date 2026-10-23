"""
Shared test isolation. Some tests import ingest.py / the AI layer with stub vector modules
(so they run without qdrant-client or ollama). This fixture snapshots the affected entries of
sys.modules and the `vectordb` package attributes, and restores them after EVERY test, so a stub
installed by one test can never leak into another (e.g. the end-to-end demo test).
"""
import sys

import pytest

_KEYS = ("vectordb.qdrant_client", "vectordb.embedder", "ingest",
         "agentic_rag.compliance_check", "recommender.resolution_recommender")


@pytest.fixture(autouse=True)
def _isolate_stubbed_modules():
    saved = {k: sys.modules.get(k) for k in _KEYS}
    pkg = sys.modules.get("vectordb")
    saved_attrs = {a: getattr(pkg, a) for a in ("qdrant_client", "embedder") if pkg and hasattr(pkg, a)}
    yield
    for k, mod in saved.items():
        if mod is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = mod
    pkg = sys.modules.get("vectordb")
    if pkg is not None:
        for a in ("qdrant_client", "embedder"):
            if a in saved_attrs:
                setattr(pkg, a, saved_attrs[a])
            elif hasattr(pkg, a):
                delattr(pkg, a)
