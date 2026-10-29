"""
standards_corpus/seed_standards.py

PLACEHOLDER standards corpus: illustrative paraphrases of AWS D1.1, ASME B31.3 and IS 800, NOT
verbatim code text. They must be replaced with PRAJ's referenced standards before any real use.

Standards are stored in QDRANT ONLY (collection standards_chunks); nothing is written to Postgres.
Point ids are stable positive 63-bit integers derived from (code_reference, section_reference,
chunk text), so re-seeding overwrites the same points instead of adding duplicates.

Usage:
    python standards_corpus/seed_standards.py            # upsert into the existing collection
    python standards_corpus/seed_standards.py --recreate # DESTRUCTIVE: drop + recreate the collection first
"""
import argparse
import hashlib
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vectordb import qdrant_client as vdb
from vectordb import embedder

# [PLACEHOLDER CONTENT — swap for real PRAJ standards before production use]
# Every chunk is stored in Qdrant with corpus_status = CORPUS_STATUS; the RAG result and the
# recommender report it, so a demo can never present these paraphrases as authoritative.
CORPUS_STATUS = "illustrative_placeholder"
PLACEHOLDER_STANDARDS = [
    {
        "title": "AWS D1.1 — Structural Welding Code (illustrative excerpt)",
        "code_reference": "AWS D1.1",
        "discipline": "Structural/Piping",
        "chunks": [
            {"section_reference": "Clause 2.4", "chunk_text":
                "Weld size for fillet welds shall be determined based on the thickness of the thinner part joined, "
                "unless a larger size is required by calculated stress. Minimum fillet weld sizes are tabulated "
                "by base metal thickness ranges."},
            {"section_reference": "Clause 7.2.1", "chunk_text":
                "All welds shall be visually inspected prior to acceptance. Visual inspection criteria include "
                "absence of cracks, adequate fusion, acceptable profile, and freedom from overlap."},
            {"section_reference": "Table 2.1", "chunk_text":
                "Minimum weld symbol designation on drawings shall indicate weld type, size, length, and process "
                "where the weld deviates from standard shop practice."},
        ],
    },
    {
        "title": "ASME B31.3 — Process Piping (illustrative excerpt)",
        "code_reference": "ASME B31.3",
        "discipline": "Piping",
        "chunks": [
            {"section_reference": "Section 321", "chunk_text":
                "Pipe supports shall be spaced such that span does not induce stresses or deflections exceeding "
                "allowable limits for the pipe size, schedule, and operating conditions."},
            {"section_reference": "Section 300.2", "chunk_text":
                "Each piping line shall be assigned a line designation including line number, size, piping class, "
                "and insulation/tracing requirements as applicable, shown on the drawing's line list."},
        ],
    },
    {
        "title": "IS 800 — General Construction in Steel (illustrative excerpt)",
        "code_reference": "IS 800",
        "discipline": "Structural",
        "chunks": [
            {"section_reference": "Clause 10.2.4", "chunk_text":
                "Bolted connections shall specify bolt grade, diameter, and tightening torque. Minimum edge "
                "distance and pitch requirements are tabulated based on bolt diameter."},
            {"section_reference": "Clause 7.1", "chunk_text":
                "Permissible dimensional tolerance for fabricated structural members shall not exceed the limits "
                "specified in Table 4, varying by member length and cross-section type."},
        ],
    },
]


def chunk_point_id(code_reference: str, section_reference: str, chunk_text: str) -> int:
    """Deterministic positive 63-bit integer id (same chunk -> same id on every run)."""
    digest = hashlib.sha256(f"{code_reference}\x1f{section_reference}\x1f{chunk_text}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF or 1


def standards_points(standards: List[Dict] = None) -> List[Dict]:
    """Every chunk as {id, text, payload}; vectors are added by seed()."""
    out = []
    for std in standards or PLACEHOLDER_STANDARDS:
        for c in std["chunks"]:
            out.append({
                "id": chunk_point_id(std["code_reference"], c["section_reference"], c["chunk_text"]),
                "text": c["chunk_text"],
                "payload": {"code_reference": std["code_reference"], "section_reference": c["section_reference"],
                            "page_number": c.get("page_number"), "chunk_text": c["chunk_text"],
                            "title": std["title"], "corpus_status": CORPUS_STATUS},
            })
    return out


def seed(recreate: bool = False, standards: List[Dict] = None) -> Dict:
    """Embed and upsert all chunks into Qdrant. -> {"upserted": n, "failed": [section, ...]}"""
    if recreate:
        vdb.recreate_collection(vdb.STANDARDS_COLLECTION)
    vdb.ensure_collections()
    items, failed = [], []
    for p in standards_points(standards):
        try:
            items.append({"id": p["id"], "vector": embedder.embed_text(p["text"]), "payload": p["payload"]})
        except Exception as e:
            failed.append(f"{p['payload']['code_reference']} {p['payload']['section_reference']}: {e}")
    vdb.upsert_standards_points(items)
    return {"collection": vdb.STANDARDS_COLLECTION, "upserted": len(items), "failed": failed,
            "corpus_status": CORPUS_STATUS}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recreate", action="store_true", help="drop and recreate the standards collection first")
    args = ap.parse_args(argv)
    result = seed(recreate=args.recreate)
    print(f"Upserted {result['upserted']} chunk(s) into {result['collection']}; failed: {len(result['failed'])}")
    for f in result["failed"]:
        print(f"  {f}")
    print("REMINDER: this is placeholder content; swap for PRAJ's real standards before production use.")
    return result


if __name__ == "__main__":
    main()
