"""
scripts/demo_pipeline.py -- one reproducible path: PDF -> extraction -> classification ->
ingest (PostgreSQL + Qdrant) -> historical retrieval + standards RAG -> DRAFT recommendation.

All data is SYNTHETIC (generated here, non-confidential). Real components used:
comment_extractor.py (CLI), ingest.py, database/db.py on a real PostgreSQL, vectordb/qdrant_client.py
on a real Qdrant (in-memory by default), agentic_rag + recommender unchanged.

Stand-ins, chosen with flags and printed in the output:
  --llm mock          (default) deterministic scripted LLM: shows control flow and evidence
                      gating, NOT model quality. --llm openrouter uses config.yaml + OPENROUTER_API_KEY.
  --embedder hash     (default) deterministic bag-of-words hashing: LEXICAL, not semantic.
                      --embedder ollama uses nomic-embed-text (needs Ollama running).
  --qdrant memory     (default) qdrant-client local mode, no server. --qdrant server uses QDRANT_HOST/PORT
                      and ONLY its own collections cems_demo_comments / cems_demo_standards_chunks
                      (recreated each run). The team collections 'comments' / 'standards_chunks' are
                      never deleted or written. (Before this fix server mode deleted them.)
The standards are the repo's ILLUSTRATIVE placeholders, never real code text.

Database: --dsn must point at a server where the user may CREATE DATABASE (e.g. the
docker-compose Postgres). The demo creates its own database `cems_demo` (final 3-table schema) and
never touches `cems`; an existing `cems_demo` is only replaced with --recreate-demo-db.
--qdrant server uses only the collections cems_demo_comments / cems_demo_standards_chunks.

    python scripts/demo_pipeline.py --dsn postgresql://cems:cems_dev_password@localhost:5432/postgres
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HISTORICAL = [((120, 120), "Verify fillet weld size per AWS D1.1 for the support bracket"),
              ((420, 220), "Title block font too small to read"),
              ((620, 380), "Relocate valve V-12 to keep maintenance clearance")]
HISTORICAL_RESOLUTIONS = ["Fillet weld increased to 6 mm per the thinner-part rule; bracket detail revised.",
                          "Title block text height increased to 3.5 mm.",
                          "Valve V-12 moved 300 mm east; clearance envelope added to the layout."]
NEW = [((150, 140), "Fillet weld size on support bracket does not follow AWS D1.1, verify weld size"),
       ((450, 260), "Font in title block is too small"),
       ((650, 420), "Add insulation to line 4in-CS-102")]

STANDARDS_KEYWORDS = ("weld", "aws", "asme", "is 800", "bolt", "pipe support", "tolerance", "line designation")
# What a decomposition step would ask for each topic (the mock's scripted "reasoning").
MOCK_SUBQUERIES = {"weld": "What fillet weld size is required, based on the thickness of the thinner part joined?",
                   "bolt": "What must be specified for bolted connections?",
                   "tolerance": "What dimensional tolerance applies to fabricated members?"}
LEXICAL_MIN_SIMILARITY = 0.5   # history threshold used ONLY with the hash stand-in (default is 0.55)


# ---------------------------------------------------------------- stand-ins

def hash_embed(text: str, dim: int = 768):
    """Deterministic LEXICAL embedding (hashed unigrams+bigrams, L2-normalised). Not semantic."""
    words = re.findall(r"[a-z0-9.]+", (text or "").lower())
    feats = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
    v = [0.0] * dim
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 64) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class MockLLM:
    """Deterministic, rule-based replies in the exact JSON shapes the pipeline expects.
    It demonstrates control flow and the evidence gates; it is NOT an AI model."""
    label = "MOCK LLM (scripted, deterministic): demonstrates control flow, not model quality"

    def chat_json(self, system, user):
        if "searchable questions" in system:
            comment = re.search(r'Comment: "(.*)"', user, re.S).group(1)
            low = comment.lower()
            if not any(k in low for k in STANDARDS_KEYWORDS):
                return {"subqueries": []}
            return {"subqueries": [q for k, q in MOCK_SUBQUERIES.items() if k in low] or [comment]}
        if "ONLY the provided" in system:
            m = re.search(r"\[S1\] \[([^\]]+)\]: (.*?)(?:\n\n\[S2\]|$)", user, re.S)
            return {"answer": f"[S1] {m.group(1)}: {m.group(2).strip()}", "citations": ["S1"], "sufficient": True}
        if "fact-checker" in system:
            return {"passed": True, "notes": "mock check: answer quotes the excerpt verbatim"}
        if "draft a suggested" in system:
            parts = []
            hist = re.findall(r'resolved as: "(.*?)"', user)
            if hist:
                parts.append(f"Following precedent: {hist[0]}")
            std = re.search(r"\[sources: (.*?)\]", user)
            if std:
                parts.append(f"Confirm against {std.group(1)} (illustrative corpus) before approval.")
            return {"draft_resolution": " ".join(parts) or "No supporting evidence found; reviewer to decide.",
                    "basis": "both" if hist and std else "similar_comments" if hist else "standards" if std else "generic"}
        raise ValueError(f"unexpected prompt: {system[:40]}")


# ---------------------------------------------------------------- steps

def make_pdf(path: Path, items, marker: str):
    import fitz
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((40, 560), marker, fontsize=8)
    for pos, text in items:
        a = page.add_text_annot(pos, text)
        a.set_info(title="Synthetic Reviewer")
        a.update()
    doc.save(path)


def run_extractor(workdir: Path):
    import yaml
    import comment_extractor as ce
    y = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    y["vision"]["enabled"] = False
    y["llm"]["metadata_enabled"] = False
    y.setdefault("classification", {})["llm_enabled"] = False
    y.setdefault("ocr", {})["enabled"] = False
    y.setdefault("enrichment", {})["enabled"] = False
    cfg_path = workdir / "demo_offline.yaml"
    cfg_path.write_text(yaml.safe_dump(y), encoding="utf-8")
    old_argv, old_cwd = sys.argv, os.getcwd()
    os.chdir(workdir)
    try:
        sys.argv = ["comment_extractor.py", "--input", "input", "--config", str(cfg_path)]
        ce.main()
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    return workdir / "output" / "master_comments.csv"


DEMO_COLLECTIONS = ("cems_demo_comments", "cems_demo_standards_chunks")
DEMO_PROJECT, DEMO_SUPPLIER, DEMO_PO = "PRJ", "Demo Supplier (synthetic)", "PO-DEMO-001"


class DemoDatabaseExists(RuntimeError):
    pass


def create_database(dsn: str, name: str, recreate: bool = False):
    import psycopg2
    if name in ("cems", "postgres", "template0", "template1"):
        raise ValueError(f"refusing to (re)create database {name!r}")
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    if cur.fetchone():
        if not recreate:
            admin.close()
            raise DemoDatabaseExists(f"database {name!r} already exists; re-run with --recreate-demo-db "
                                     f"to drop and recreate it (only {name!r} is affected)")
        cur.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    cur.execute(f'CREATE DATABASE "{name}"')
    admin.close()
    u = urlparse(dsn)
    conn = psycopg2.connect(host=u.hostname, port=u.port or 5432, dbname=name, user=u.username,
                            password=u.password or "")
    conn.autocommit = True
    conn.cursor().execute((ROOT / "database/schema.sql").read_text(encoding="utf-8"))
    return conn, u


def _comments_of(conn, drawing: str):
    cur = conn.cursor()
    cur.execute("""SELECT c.id, c.comment_id, c.actual_extracted_comment FROM comments c
                   JOIN documents d ON d.id = c.document_id
                   WHERE d.praj_document_number = %s ORDER BY c.id""", (drawing,))
    return cur.fetchall()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default=os.getenv("CEMS_TEST_DATABASE_URL"),
                    help="admin DSN of a Postgres server (database 'cems_demo' is created)")
    ap.add_argument("--workdir", default="demo_run")
    ap.add_argument("--llm", choices=["mock", "openrouter"], default="mock")
    ap.add_argument("--embedder", choices=["hash", "ollama"], default="hash")
    ap.add_argument("--qdrant", choices=["memory", "server"], default="memory")
    ap.add_argument("--recreate-demo-db", action="store_true",
                    help="drop and recreate an existing 'cems_demo' database (never touches 'cems')")
    args = ap.parse_args(argv)
    if not args.dsn:
        ap.error("--dsn (or CEMS_TEST_DATABASE_URL) is required")

    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    banner = [f"LLM: {MockLLM.label if args.llm == 'mock' else 'OpenRouter model from config.yaml'}",
              f"Embeddings: {'hash (lexical stand-in, NOT semantic); history threshold ' + str(LEXICAL_MIN_SIMILARITY) if args.embedder == 'hash' else 'Ollama nomic-embed-text'}",
              f"Qdrant: {'in-memory (qdrant-client local mode)' if args.qdrant == 'memory' else 'server, demo collections ' + ', '.join(DEMO_COLLECTIONS)}",
              "Standards corpus: ILLUSTRATIVE placeholders, not real code text",
              "Data: synthetic PDFs generated by this script"]
    print("\n".join(["=" * 78, "CEMS demonstration", *banner, "=" * 78]))

    # 1. synthetic drawings
    make_pdf(workdir / "input/PRJ_PID_DWG100_RA.pdf", HISTORICAL, "historical drawing (synthetic)")
    make_pdf(workdir / "input/PRJ_PID_DWG200_RA.pdf", NEW, "new drawing under review (synthetic)")

    # 2. extraction + classification (real CLI, offline config)
    master = run_extractor(workdir)

    # 3. services: own database, own (or in-memory) collections
    from database import db
    from vectordb import qdrant_client as vdb
    from vectordb import embedder, comment_sync
    conn, u = create_database(args.dsn, "cems_demo", recreate=args.recreate_demo_db)
    if db._pool is not None:
        db._pool.closeall()
        db._pool = None
    db.init_pool(host=u.hostname, port=u.port or 5432, dbname="cems_demo", user=u.username, password=u.password or "")
    if args.qdrant == "memory":
        from qdrant_client import QdrantClient
        vdb._client = QdrantClient(location=":memory:")
    else:
        vdb.COMMENTS_COLLECTION, vdb.STANDARDS_COLLECTION = DEMO_COLLECTIONS
        existing = {c.name for c in vdb.get_client().get_collections().collections}
        for name in DEMO_COLLECTIONS:              # only the demo's own collections, never the team's
            if name in existing:
                vdb.get_client().delete_collection(name)
    vdb.ensure_collections()
    if args.embedder == "hash":
        embedder.embed_text = hash_embed
    llm = MockLLM() if args.llm == "mock" else None
    if llm is None:
        import comment_extractor as ce
        llm = ce.LLMClient(ce.Config.from_yaml(ROOT / "config.yaml"))

    # 4. ingest (real loader) + embedding sync
    import ingest
    totals = ingest.ingest_dataframe(ingest.read_extractor_csv(master), str(master),
                                     DEMO_PROJECT, DEMO_SUPPLIER, DEMO_PO)
    print(f"\nIngest: inserted={totals['comments']} embedded={totals['embedded']} "
          f"skipped={len(totals['skipped'])} conflicts={len(totals['conflicts'])}")

    # 5. illustrative standards -> Qdrant only
    from standards_corpus import seed_standards as seed
    seeded = seed.seed()

    # 6. synthetic HUMAN resolutions for the historical drawing (status 'closed', payload updated)
    for (cid, _uid, _text), text in zip(_comments_of(conn, "DWG100"), HISTORICAL_RESOLUTIONS):
        comment_sync.resolve_comment(cid, text)

    # 7. AI drafts for every comment of the new drawing (stored as ai_suggested_resolution only)
    from recommender.resolution_recommender import suggest_resolution
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "stand_ins": banner, "ingest": totals,
              "standards": seeded, "comments": []}
    min_sim = LEXICAL_MIN_SIMILARITY if args.embedder == "hash" else 0.55
    for cid, uid, text in _comments_of(conn, "DWG200"):
        r = suggest_resolution(cid, llm, min_similarity=min_sim)
        stored = db.get_comment_context(cid)
        report["comments"].append({
            "id": cid, "comment_id": uid, "comment": text,
            **{k: r[k] for k in ("status", "requires_human_approval", "auto_applied", "draft_resolution",
                                 "basis", "model_claimed_basis", "confidence_percent", "confidence_rationale",
                                 "uncertainty", "corpus_status", "citations", "faithfulness_failed", "saved")},
            "historical_examples": [{"text": s["text"], "resolution": s["resolution_text"],
                                     "score": round(s["score"], 3), "comment_id": s["comment_id"]}
                                    for s in r["similar_comments"]],
            "standards_evidence_status": r["standards_grounding"]["evidence_status"] if r["standards_grounding"] else None,
            "standards_evidence": [f"{e['code_reference']} {e['section_reference']}" for e in r["standards_evidence"]],
            "stored_ai_suggested_resolution": stored["ai_suggested_resolution"],
            "stored_ai_confidence_percent": stored["ai_confidence_percent"],
            "stored_status": stored["status"], "stored_resolution_text": stored["resolution_text"],
            "trace": r["trace"]})
        print(f"\n--- {uid}\nComment : {text}\nStatus  : {r['status']} (human approval required, auto_applied=False)"
              f"\nDraft   : {r['draft_resolution']}\nBasis   : {r['basis']} (model claimed: {r['model_claimed_basis']})"
              f"\nHistory : {[s['comment_id'] for s in r['similar_comments']] or 'none'}"
              f"\nStandards: {report['comments'][-1]['standards_evidence_status']} {report['comments'][-1]['standards_evidence']}"
              f" [corpus: {r['corpus_status']}]\nConfidence: {r['confidence_percent']} ({r['confidence_rationale']})"
              f"\nUncertainty: {r['uncertainty'] or 'none'}")
    out = workdir / "demo_report.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out}")
    db._pool.closeall()
    db._pool = None
    conn.close()
    return report


if __name__ == "__main__":
    try:
        main()
    except DemoDatabaseExists as e:
        print(f"Refusing to continue: {e}")
        sys.exit(2)
