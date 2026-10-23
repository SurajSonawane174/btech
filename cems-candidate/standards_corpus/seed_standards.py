"""
standards_corpus/seed_standards.py

PLACEHOLDER standards corpus — 3 realistic excerpts covering welding,
piping, and structural steel, so the agentic RAG pipeline has something
real to retrieve against tonight. These are illustrative paraphrases,
NOT verbatim legal text of the actual codes, and MUST be swapped for
PRAJ's actual referenced standards before this is used for anything
beyond a demo.

Usage:
    python seed_standards.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import db
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


def seed():
    db.init_pool()
    vdb.ensure_collections()

    total_chunks = 0
    for std in PLACEHOLDER_STANDARDS:
        doc_id = db.get_or_create_standards_document(
            title=std["title"], code_reference=std["code_reference"], discipline=std["discipline"]
        )
        chunk_records = [
            {"chunk_index": i, "chunk_text": c["chunk_text"], "section_reference": c["section_reference"]}
            for i, c in enumerate(std["chunks"])
        ]
        inserted = db.insert_standards_chunks_bulk(doc_id, chunk_records)   # idempotent

        # Embed + push to Qdrant
        unembedded = db.get_unembedded_standards_chunks(limit=100)
        items, chunk_ids = [], []
        for chunk in unembedded:
            vector = embedder.embed_text(chunk["chunk_text"])
            items.append({
                "chunk_id": chunk["id"], "vector": vector, "text": chunk["chunk_text"],
                "code_reference": chunk["code_reference"], "section_reference": chunk["section_reference"],
                "title": chunk["title"],
                "corpus_status": CORPUS_STATUS,
            })
            chunk_ids.append(chunk["id"])
        if items:
            vdb.upsert_standards_chunk_embeddings_bulk(items)
            db.mark_standards_chunks_embedded(chunk_ids)
            total_chunks += len(items)

        print(f"Seeded {std['code_reference']}: {inserted} new of {len(std['chunks'])} chunks")

    print(f"\nTotal chunks embedded: {total_chunks}")
    print("REMINDER: this is placeholder content — swap for PRAJ's real standards before production use.")


if __name__ == "__main__":
    seed()
