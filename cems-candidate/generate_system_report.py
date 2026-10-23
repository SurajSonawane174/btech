"""
generate_system_report.py

Runs the live checks of the standalone CEMS AI engine against configured services and writes a
PDF (plus a JSON copy of the raw results). Every status in the report is derived from what
happened in THIS run; nothing is hard-coded as "verified".

Each check ends in exactly one gate status:
    PASS            the check ran against the real service and met its pass criterion
    FAIL            it ran, but the result did not meet the criterion (e.g. RAG not verified)
    ERROR           it raised (service down, bad credentials, schema missing, ...)
    NOT_CONFIGURED  a prerequisite is missing (e.g. no OPENROUTER_API_KEY); nothing was called
    NO_DATA         the service answered but the data the check needs is not there
The overall verdict is "ALL LIVE CHECKS PASSED" only when every gate is PASS; the exit code is
0 in that case and 1 otherwise.

Paths do not depend on the working directory: config defaults to config.yaml next to this file
and the report is written next to this file unless --out is given.

Targets:
    --target main  (default) database POSTGRES_DB (default 'cems'), collections 'comments' /
                   'standards_chunks' (QDRANT_*_COLLECTION env vars override)
    --target demo  database 'cems_demo' and collections cems_demo_comments /
                   cems_demo_standards_chunks, i.e. what
                   scripts/demo_pipeline.py --qdrant server --embedder ollama  writes.
The semantic-search and recommender checks use the demo's synthetic texts. On a database without
that data the semantic check reports NO_DATA instead of passing.

Read-only apart from audit traces: the report never creates, deletes or writes collections,
tables, comments or resolutions. The one write is the normal rag_query_traces audit row that
check_compliance() stores when the recommender runs for a comment found in the database.

Usage:
    python generate_system_report.py [--target demo] [--config PATH] [--out PATH]
                                     [--junit pytest.xml] [--evaluation eval_report.json]
"""
import argparse
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional
from xml.sax.saxutils import escape as _xml_escape

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

def _esc(value) -> str:
    return _xml_escape("" if value is None else str(value))


PASS, FAIL, ERROR, NOT_CONFIGURED, NO_DATA = "PASS", "FAIL", "ERROR", "NOT_CONFIGURED", "NO_DATA"
DEMO_DB = "cems_demo"
DEMO_COLLECTIONS = ("cems_demo_comments", "cems_demo_standards_chunks")

# Queries for the CURRENT synthetic demo (scripts/demo_pipeline.py HISTORICAL / NEW texts).
# expected: texts that count as a correct top hit; None = the query is unrelated to all demo data.
WELD_TEXTS = ("Verify fillet weld size per AWS D1.1 for the support bracket",
              "Fillet weld size on support bracket does not follow AWS D1.1, verify weld size")
FONT_TEXTS = ("Title block font too small to read", "Font in title block is too small")
SEMANTIC_QUERIES = [
    ("Verify fillet weld size per AWS D1.1 for the support bracket", "exact", WELD_TEXTS),
    ("Check the support bracket fillet weld dimension against AWS D1.1", "paraphrase", WELD_TEXTS),
    ("The lettering in the title block cannot be read, make it bigger", "paraphrase", FONT_TEXTS),
    ("Provide a lifting lug on the pump base frame", "unrelated", None),
]
RAG_COMMENT = "Fillet weld size on support bracket does not follow AWS D1.1, verify weld size"
RECOMMENDER_COMMENTS = [
    "Fillet weld size on support bracket does not follow AWS D1.1, verify weld size",
    "Font in title block is too small",
    "Add insulation to line 4in-CS-102",
]
EXACT_MIN_SCORE = 0.95


# ============================================================ checks (each returns raw data)

def apply_target(target: str) -> Dict:
    from vectordb import qdrant_client as vdb
    if target == "demo":
        vdb.COMMENTS_COLLECTION, vdb.STANDARDS_COLLECTION = DEMO_COLLECTIONS
        dbname = DEMO_DB
    else:
        dbname = os.getenv("POSTGRES_DB", "cems")
    return {"target": target, "database": dbname, "comments_collection": vdb.COMMENTS_COLLECTION,
            "standards_collection": vdb.STANDARDS_COLLECTION}


def check_infrastructure(ctx: Dict) -> Dict:
    from database import db
    from vectordb import qdrant_client as vdb
    if db._pool is None:
        db.init_pool(dbname=ctx["database"])
    counts = {}
    with db.get_cursor() as cur:
        for label, sql in (("postgres_comments", "SELECT count(*) AS n FROM comments"),
                           ("postgres_embedded", "SELECT count(*) AS n FROM comments WHERE embedded = true"),
                           ("postgres_projects", "SELECT count(*) AS n FROM projects"),
                           ("postgres_revisions", "SELECT count(*) AS n FROM revisions"),
                           ("postgres_resolutions_human",
                            "SELECT count(*) AS n FROM resolutions WHERE source <> 'ai_suggested'"),
                           ("postgres_standards_chunks", "SELECT count(*) AS n FROM standards_chunks")):
            cur.execute(sql)
            counts[label] = cur.fetchone()["n"]
    client = vdb.get_client()
    existing = {c.name for c in client.get_collections().collections}
    for label, name in (("qdrant_comments_points", vdb.COMMENTS_COLLECTION),
                        ("qdrant_standards_points", vdb.STANDARDS_COLLECTION)):
        counts[label] = client.get_collection(name).points_count if name in existing else None
    return counts


def check_semantic_search(ctx: Dict) -> List[Dict]:
    from vectordb import embedder
    from vectordb.qdrant_client import search_similar_comments
    rows = []
    for query, kind, expected in SEMANTIC_QUERIES:
        hits = search_similar_comments(embedder.embed_text(query), top_k=5, score_threshold=0.0)
        top = hits[0] if hits else None
        rows.append({"query": query, "kind": kind, "expected": list(expected) if expected else None,
                     "top_match": top["text"] if top else None,
                     "score": round(float(top["score"]), 4) if top else None,
                     "expected_present": bool(expected) and any(h["text"] in expected for h in hits)})
    return rows


def _llm_or_none(cfg_path: Path):
    from comment_extractor import Config, LLMClient
    cfg = Config.from_yaml(cfg_path)
    if not os.getenv(cfg.llm_api_key_env):
        return None, cfg.llm_api_key_env
    return LLMClient(cfg), cfg.llm_api_key_env


def check_agentic_rag(ctx: Dict) -> Dict:
    from agentic_rag.compliance_check import check_compliance
    llm, key_name = _llm_or_none(ctx["config_path"])
    if llm is None:
        return {"not_configured": f"{key_name} is not set"}
    r = check_compliance(RAG_COMMENT, llm)
    return {"comment": RAG_COMMENT, "answer": r.get("answer"), "cited_sections": r.get("cited_sections", []),
            "faithfulness_passed": r.get("faithfulness_passed"), "faithfulness_notes": r.get("faithfulness_notes"),
            "hops": r.get("hops", []), "verified": r.get("verified") is True,
            "evidence_status": r.get("evidence_status", "unknown"),
            "corpus_status": r.get("corpus_status", "unknown"), "citation_check": r.get("citation_check", {})}


def _comment_id_for(text: str) -> Optional[str]:
    from database import db
    with db.get_cursor() as cur:
        cur.execute("SELECT id::text AS id FROM comments WHERE actual_extracted_comment = %s "
                    "ORDER BY created_at DESC LIMIT 1", (text,))
        row = cur.fetchone()
    return row["id"] if row else None


def check_recommender(ctx: Dict) -> List[Dict]:
    from recommender.resolution_recommender import recommend_resolution
    llm, key_name = _llm_or_none(ctx["config_path"])
    if llm is None:
        return [{"not_configured": f"{key_name} is not set"}]
    rows = []
    for comment in RECOMMENDER_COMMENTS:
        cid = _comment_id_for(comment)
        r = recommend_resolution(comment, llm, comment_id=cid)
        rows.append({"comment": comment, "comment_id_found": cid is not None,
                     "draft": r.get("draft_resolution"), "status": r.get("status"),
                     "requires_human_approval": r.get("requires_human_approval"),
                     "auto_applied": r.get("auto_applied"), "basis": r.get("basis"),
                     "confidence": r.get("confidence_percent"), "n_similar": len(r.get("similar_comments") or []),
                     "standards_status": (r.get("standards_grounding") or {}).get("evidence_status"),
                     "corpus_status": r.get("corpus_status"), "uncertainty": r.get("uncertainty", [])})
    return rows


CHECKS: List[tuple] = [
    ("infrastructure", "PostgreSQL + Qdrant reachable, read-only counts", check_infrastructure),
    ("semantic_search", "Similar-comment retrieval on the demo texts (Ollama embeddings + Qdrant)", check_semantic_search),
    ("agentic_rag", "Standards RAG: decomposition, retrieval, citation validation, faithfulness (real LLM)", check_agentic_rag),
    ("recommender", "Draft recommendations stay drafts requiring human approval (real LLM)", check_recommender),
]


def run_checks(ctx: Dict, checks=None) -> Dict[str, Dict]:
    results = {}
    for name, _, fn in (checks or CHECKS):
        print(f"--- {name} ---")
        try:
            results[name] = {"ran": True, "data": fn(ctx)}
            print("ran")
        except Exception as e:
            results[name] = {"ran": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()}
            print(f"ERROR: {type(e).__name__}: {e}")
    return results


# ============================================================ gates (pure; unit-tested)

def _gate(status: str, reason: str) -> Dict:
    return {"status": status, "reason": reason}


def gate_infrastructure(res: Dict) -> Dict:
    if not res or not res.get("ran"):
        return _gate(ERROR, (res or {}).get("error", "not run"))
    d = res["data"]
    missing = [k for k in ("qdrant_comments_points", "qdrant_standards_points") if d.get(k) is None]
    if missing:
        return _gate(NO_DATA, f"Qdrant collection(s) missing: {', '.join(missing)}")
    note = ""
    if d["postgres_embedded"] != d["qdrant_comments_points"]:
        note = (f"; note: {d['postgres_embedded']} comments marked embedded in Postgres vs "
                f"{d['qdrant_comments_points']} Qdrant points")
    return _gate(PASS, "both services answered" + note)


def gate_semantic(res: Dict, min_similarity: float = 0.55) -> Dict:
    if not res or not res.get("ran"):
        return _gate(ERROR, (res or {}).get("error", "not run"))
    rows = res["data"]
    related = [r for r in rows if r["expected"]]
    if not related or not all(r["expected_present"] for r in related):
        return _gate(NO_DATA, "demo comments not found in the collection (run the demo with "
                              "--qdrant server --embedder ollama and use --target demo)")
    problems = []
    for r in related:
        if r["top_match"] not in r["expected"]:
            problems.append(f"{r['kind']} query: top hit is not an expected comment")
        elif r["kind"] == "exact" and r["score"] < EXACT_MIN_SCORE:
            problems.append(f"exact query scored {r['score']} < {EXACT_MIN_SCORE}")
        elif r["kind"] != "exact" and r["score"] < min_similarity:
            problems.append(f"paraphrase scored {r['score']} < threshold {min_similarity}")
    para = [r["score"] for r in related if r["kind"] == "paraphrase" and r["score"] is not None]
    for r in rows:
        if r["kind"] == "unrelated" and r["score"] is not None and para and r["score"] >= min(para):
            problems.append(f"unrelated query scored {r['score']}, not below the paraphrases ({min(para)})")
    if problems:
        return _gate(FAIL, "; ".join(problems))
    return _gate(PASS, f"{len(related)} related queries hit an expected comment above threshold; "
                       f"unrelated query scored lower (synthetic demo texts, {len(rows)} queries; not a quality metric)")


def gate_rag(res: Dict) -> Dict:
    if not res or not res.get("ran"):
        return _gate(ERROR, (res or {}).get("error", "not run"))
    d = res["data"]
    if "not_configured" in d:
        return _gate(NOT_CONFIGURED, d["not_configured"])
    if d.get("verified") is not True:
        return _gate(FAIL, f"not verified: evidence_status={d.get('evidence_status')}")
    corpus = d.get("corpus_status")
    suffix = "" if corpus == "approved" else f" (corpus is {corpus}: shows the mechanism, not real compliance)"
    return _gate(PASS, "answer verified (citations validated in code + faithfulness check)" + suffix)


def gate_recommender(res: Dict) -> Dict:
    if not res or not res.get("ran"):
        return _gate(ERROR, (res or {}).get("error", "not run"))
    rows = res["data"]
    if rows and "not_configured" in rows[0]:
        return _gate(NOT_CONFIGURED, rows[0]["not_configured"])
    if not rows:
        return _gate(NO_DATA, "no recommendations produced")
    unsafe = [r["comment"] for r in rows if r.get("auto_applied") is not False
              or r.get("requires_human_approval") is not True]
    if unsafe:
        return _gate(FAIL, f"draft safety violated for {len(unsafe)} comment(s)")
    unavailable = [r for r in rows if r.get("status") != "draft_requires_human_review"]
    if unavailable:
        return _gate(FAIL, f"{len(unavailable)} of {len(rows)} drafts could not be generated")
    return _gate(PASS, f"{len(rows)} drafts generated, all require human approval, none auto-applied")


GATES: Dict[str, Callable[[Dict], Dict]] = {
    "infrastructure": gate_infrastructure, "semantic_search": gate_semantic,
    "agentic_rag": gate_rag, "recommender": gate_recommender,
}


def evaluate_gates(results: Dict[str, Dict]) -> Dict[str, Dict]:
    """A check that is missing from `results` is ERROR ("not run"), never PASS."""
    return {name: GATES[name](results.get(name)) for name in GATES}


def overall_verdict(gates: Dict[str, Dict]) -> Dict:
    counts: Dict[str, int] = {}
    for g in gates.values():
        counts[g["status"]] = counts.get(g["status"], 0) + 1
    all_pass = bool(gates) and all(g["status"] == PASS for g in gates.values())
    text = ("ALL LIVE CHECKS PASSED" if all_pass else
            "NOT ALL LIVE CHECKS PASSED: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items()) if s != PASS))
    return {"all_passed": all_pass, "counts": counts, "text": text}


def read_junit(path: Optional[Path]) -> Optional[Dict]:
    """Counts from a pytest --junitxml file. None when not given; {'error': ...} when unreadable."""
    if not path:
        return None
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        tot = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        tot["passed"] = tot["tests"] - tot["failures"] - tot["errors"] - tot["skipped"]
        tot["file"] = Path(path).name
        tot["timestamp"] = suites[0].get("timestamp") if suites else None
        return tot
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def read_evaluation(path: Optional[Path]) -> Optional[Dict]:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ============================================================ PDF

NOT_VERIFIED_BY_THIS_REPORT = [
    "Extraction and classification accuracy: needs a labelled real-PDF dataset "
    "(evaluation/README.md). Native-annotation coverage is not accuracy.",
    "Local OCR (LightOnOCR-2-1B): only unit-tested with a fake engine; scripts/ocr_smoke_test.py has "
    "not been reported as run.",
    "Hosted vision fallback for flattened pages: not exercised by this report.",
    "Standards compliance: the corpus is illustrative placeholder text, not PRAJ-approved code text.",
    "Retrieval quality on real comments: the semantic check uses a handful of synthetic demo texts.",
    "Access control / RBAC: not part of the standalone AI engine (owned by the PRAJ backend); "
    "database/db.py has a can() helper that nothing enforces.",
    "Human approve/edit/reject workflow: drafts are produced; no approval UI or CLI is part of this engine yet.",
]

EVIDENCE_CLASSES = [
    ("Automated unit tests", "pytest with fake LLM / fake OCR / stub or hash embeddings and synthetic "
                             "PDFs. Shows logic, not model or service quality."),
    ("Real-PostgreSQL integration tests", "pytest with CEMS_TEST_DATABASE_URL: real Postgres, "
                                          "in-memory Qdrant, stubbed embeddings. Skipped when the variable is unset."),
    ("Live checks (this report)", "real PostgreSQL, Qdrant server, Ollama embeddings and the configured "
                                  "LLM, as far as each is configured. Gate statuses below."),
    ("Manual validation", "none recorded by this tool."),
]


def build_pdf(out_path: Path, ctx: Dict, results: Dict, gates: Dict, verdict: Dict,
              junit: Optional[Dict], evaluation: Optional[Dict]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceBefore=14, spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=6)
    body = ParagraphStyle("B", parent=ss["Normal"], fontSize=10, leading=14, spaceAfter=6)
    cell = ParagraphStyle("C", parent=ss["Normal"], fontSize=8, leading=10)
    ok = ParagraphStyle("OK", parent=body, textColor=colors.HexColor("#0a7d2c"))
    bad = ParagraphStyle("BAD", parent=body, textColor=colors.HexColor("#c0392b"))
    caveat = ParagraphStyle("CAV", parent=ss["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#8b0000"),
                            borderColor=colors.HexColor("#8b0000"), borderWidth=0.5, borderPadding=6,
                            backColor=colors.HexColor("#fff3f3"), spaceAfter=6)

    def table(rows, widths):
        t = Table([[Paragraph(_esc(str(c)), cell) for c in r] for r in rows], colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
                               ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    s = []
    s.append(Paragraph("CEMS AI engine: live check report", ss["Title"]))
    s.append(Paragraph(f"Generated {_esc(ctx['generated'])} | target: {_esc(ctx['target'])} "
                       f"(database {_esc(ctx['database'])}, collections {_esc(ctx['comments_collection'])} / "
                       f"{_esc(ctx['standards_collection'])})", body))
    s.append(Paragraph(f"<b>Verdict: {_esc(verdict['text'])}</b>", ok if verdict["all_passed"] else bad))
    s.append(Paragraph("Every status below was computed from this run. A check that did not run, or "
                       "whose prerequisite is missing, is never counted as passed.", body))

    s.append(Paragraph("1. Gate summary", h1))
    rows = [["Check", "What it tests", "Status", "Reason"]]
    for name, desc, _ in CHECKS:
        g = gates[name]
        rows.append([name, desc, g["status"], g["reason"]])
    s.append(table(rows, [2.8 * cm, 4.6 * cm, 3.1 * cm, 6.5 * cm]))

    s.append(Paragraph("2. Kinds of evidence", h1))
    s.append(table([["Evidence", "Meaning"], *EVIDENCE_CLASSES], [5 * cm, 12 * cm]))
    if junit is None:
        s.append(Paragraph("Automated test results: not included (pass --junit with a pytest --junitxml file).", body))
    elif "error" in junit:
        s.append(Paragraph(f"Automated test results: could not read the junit file ({_esc(junit['error'])}).", bad))
    else:
        s.append(Paragraph(
            f"Automated test results from {_esc(junit['file'])} ({_esc(str(junit.get('timestamp')))}): "
            f"{junit['passed']} passed, {junit['failures']} failed, {junit['errors']} errors, "
            f"{junit['skipped']} skipped of {junit['tests']}. Skipped tests are usually the real-PostgreSQL "
            f"tests (CEMS_TEST_DATABASE_URL unset).", ok if not (junit["failures"] or junit["errors"]) else bad))

    s.append(Paragraph("3. Check details", h1))
    for name, _, _ in CHECKS:
        res = results.get(name) or {}
        s.append(Paragraph(f"{_esc(name)}: {_esc(gates[name]['status'])}", h2))
        if not res.get("ran"):
            s.append(Paragraph(_esc(res.get("error", "not run")), bad))
            continue
        data = res["data"]
        if name == "infrastructure":
            s.append(table([["Metric", "Value"], *[[k, "missing" if v is None else v] for k, v in data.items()]],
                           [8 * cm, 5 * cm]))
        elif name == "semantic_search":
            s.append(table([["Query", "Kind", "Top match", "Score"],
                            *[[r.get("query"), r.get("kind"), r.get("top_match") or "(none)", r.get("score")] for r in data]],
                           [5.5 * cm, 2 * cm, 7 * cm, 1.5 * cm]))
        elif name == "agentic_rag":
            if "not_configured" in data:
                s.append(Paragraph(_esc(data["not_configured"]), bad))
                continue
            s.append(Paragraph(f"<b>Comment:</b> {_esc(data.get('comment'))}", body))
            for hop in data.get("hops") or []:
                s.append(Paragraph(f"Hop {hop.get('hop')}: {_esc(str(hop.get('query')))} -> "
                                   f"{hop.get('chunks_retrieved')} chunk(s); error: {_esc(str(hop.get('error')))}", body))
            s.append(Paragraph(f"<b>Answer:</b> {_esc(str(data.get('answer')))}", body))
            s.append(Paragraph(f"<b>Cited sections (validated in code):</b> "
                               f"{_esc(', '.join(data.get('cited_sections') or [])) or 'none'}", body))
            s.append(Paragraph(f"<b>Evidence status:</b> {_esc(str(data.get('evidence_status')))}; corpus: "
                               f"{_esc(str(data.get('corpus_status')))}; faithfulness: "
                               f"{_esc(str(data.get('faithfulness_notes')))}", ok if data.get("verified") is True else bad))
        elif name == "recommender":
            if data and "not_configured" in data[0]:
                s.append(Paragraph(_esc(data[0]["not_configured"]), bad))
                continue
            for r in data:
                s.append(Paragraph(f"<b>Comment:</b> {_esc(str(r.get('comment')))} (stored comment found: "
                                   f"{r.get('comment_id_found')})", body))
                s.append(Paragraph(f"<b>Draft ({_esc(str(r.get('status')))}, human approval required: "
                                   f"{r.get('requires_human_approval')}, auto-applied: {r.get('auto_applied')}):</b> "
                                   f"{_esc(str(r.get('draft')))}", body))
                s.append(Paragraph(f"Basis (computed): {_esc(str(r.get('basis')))} | similar comments used: "
                                   f"{r.get('n_similar')} | standards: {_esc(str(r.get('standards_status')))} | "
                                   f"confidence heuristic: {r.get('confidence')}", body))
                if r.get("uncertainty"):
                    s.append(Paragraph(f"Uncertainty: {_esc('; '.join(r['uncertainty']))}", body))
    s.append(Paragraph("Standards corpus: illustrative paraphrases of AWS D1.1 / ASME B31.3 / IS 800 written "
                       "for demonstration. Not citable as compliance evidence.", caveat))

    s.append(PageBreak())
    s.append(Paragraph("4. Evaluation metrics", h1))
    if evaluation is None:
        s.append(Paragraph("No evaluation report supplied (--evaluation). Real-world accuracy figures: unavailable.", body))
    elif "error" in evaluation:
        s.append(Paragraph(f"Evaluation report unreadable: {_esc(evaluation['error'])}", bad))
    else:
        for ds in evaluation.get("datasets", []):
            s.append(Paragraph(f"Dataset {_esc(ds.get('name', '?'))} | kind: <b>{_esc(ds.get('kind', '?'))}</b>", h2))
            rows = [["Task", "Metric", "Value", "n"]]
            for task, m in (ds.get("metrics") or {}).items():
                if not isinstance(m, dict) or m.get("status") != "ok":
                    rows.append([task, "-", (m or {}).get("status", "unavailable") if isinstance(m, dict) else m, "-"])
                    continue
                for k, v in m.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("n",):
                        rows.append([task, k, round(v, 4) if isinstance(v, float) else v, m.get("n", "")])
            s.append(table(rows, [4 * cm, 5 * cm, 3 * cm, 2 * cm]))
        if not any(ds.get("kind") == "real" for ds in evaluation.get("datasets", [])):
            s.append(Paragraph("No real labelled dataset in the evaluation report: real-world accuracy is unavailable. "
                               "Synthetic results only show that the metric code and pipeline run.", caveat))

    s.append(Paragraph("5. Not verified by this report", h1))
    for item in NOT_VERIFIED_BY_THIS_REPORT:
        s.append(Paragraph(f"- {_esc(item)}", body))

    SimpleDocTemplate(str(out_path), pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                      leftMargin=2 * cm, rightMargin=2 * cm).build(s)


# ============================================================ main

def main(argv=None, checks=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["main", "demo"], default="main")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--out", default=None, help="PDF path (default: next to this script)")
    ap.add_argument("--junit", default=None, help="pytest --junitxml file to summarise")
    ap.add_argument("--evaluation", default=None, help="evaluation/run_evaluation.py JSON output")
    args = ap.parse_args(argv)

    import comment_extractor  # noqa: F401  (loads .env next to this file, same as the pipeline)
    stamp = datetime.now()
    out = Path(args.out) if args.out else ROOT / f"CEMS_System_Report_{stamp.strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    ctx = {"generated": stamp.strftime("%Y-%m-%d %H:%M:%S"), "config_path": Path(args.config).resolve()}
    try:
        ctx.update(apply_target(args.target))
    except Exception as e:                       # vector client not importable: every check will ERROR
        ctx.update({"target": args.target, "database": "?", "comments_collection": "?",
                    "standards_collection": "?", "target_error": str(e)})

    out.parent.mkdir(parents=True, exist_ok=True)
    results = run_checks(ctx, checks)
    gates = evaluate_gates(results)
    verdict = overall_verdict(gates)
    junit, evaluation = read_junit(args.junit), read_evaluation(args.evaluation)
    build_pdf(out, ctx, results, gates, verdict, junit, evaluation)
    out.with_suffix(".json").write_text(json.dumps(
        {"context": {k: str(v) for k, v in ctx.items()}, "verdict": verdict, "gates": gates,
         "results": {k: {kk: vv for kk, vv in v.items() if kk != "trace"} for k, v in results.items()},
         "junit": junit, "evaluation_file": args.evaluation}, indent=2, default=str), encoding="utf-8")
    print("\n" + "\n".join(f"{n:16s} {g['status']:15s} {g['reason']}" for n, g in gates.items()))
    print(f"\n{verdict['text']}\nReport: {out}\nJSON:   {out.with_suffix('.json')}")
    return 0 if verdict["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
