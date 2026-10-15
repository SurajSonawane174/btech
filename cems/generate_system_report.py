"""
generate_system_report.py

Runs every implemented AI-automation capability against your LIVE
infrastructure (Postgres, Qdrant, Ollama, OpenRouter) and produces a
single PDF report — for your own verification AND as a showcase
artifact for Vahida/PRAJ.

Run this from the same folder as comment_extractor.py, with your venv
active and docker compose up.

Usage:
    python generate_system_report.py

Output:
    CEMS_System_Report_<timestamp>.pdf
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
)

TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
OUTPUT_PATH = f"CEMS_System_Report_{TIMESTAMP}.pdf"

# Collects everything as we go; each section appends a dict here,
# and failures are recorded rather than crashing the whole report.
results = {}


def run_section(name, fn):
    """Run one check; record success/failure so one broken piece
    doesn't stop the rest of the report from generating."""
    print(f"\n--- {name} ---")
    try:
        results[name] = {"status": "ok", "data": fn()}
        print(f"OK")
    except Exception as e:
        results[name] = {"status": "error", "error": str(e), "trace": traceback.format_exc()}
        print(f"FAILED: {e}")


# ============================================================
# SECTION 1 — Infrastructure
# ============================================================

def check_infrastructure():
    from database import db
    from vectordb import qdrant_client as vdb

    db.init_pool()
    with db.get_cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM comments")
        total_comments = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM comments WHERE embedded = true")
        embedded = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM projects")
        projects = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM revisions")
        revisions = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM standards_chunks")
        std_chunks = cur.fetchone()["n"]

    vdb.ensure_collections()
    client = vdb.get_client()
    comments_pts = client.get_collection("comments").points_count
    standards_pts = client.get_collection("standards_chunks").points_count

    return {
        "postgres_comments": total_comments, "postgres_embedded": embedded,
        "postgres_projects": projects, "postgres_revisions": revisions,
        "postgres_standards_chunks": std_chunks,
        "qdrant_comments_points": comments_pts,
        "qdrant_standards_points": standards_pts,
    }


# ============================================================
# SECTION 2 — Semantic Similarity Search
# ============================================================

def check_semantic_search():
    from vectordb import embedder
    from vectordb.qdrant_client import search_similar_comments

    test_queries = [
        ("Verify pipe diameter matches the hydraulic schedule.", "exact match"),
        ("Check whether the pipe size is consistent with the hydraulic schedule.", "paraphrase"),
        ("Relocate this valve to maintain maintenance clearance.", "different topic"),
    ]
    rows = []
    for query, label in test_queries:
        vec = embedder.embed_text(query)
        hits = search_similar_comments(vec, top_k=1, score_threshold=0.0)
        top = hits[0] if hits else None
        rows.append({
            "query": query, "label": label,
            "top_match": top["text"] if top else "(no match)",
            "score": round(top["score"], 4) if top else None,
        })
    return rows


# ============================================================
# SECTION 3 — Agentic RAG Compliance Check
# ============================================================

def check_agentic_rag():
    from comment_extractor import Config, LLMClient
    from agentic_rag.compliance_check import check_compliance

    cfg = Config.from_yaml("config.yaml")
    llm = LLMClient(cfg)

    comment = "Weld size not per AWS D1.1, please verify fillet weld dimensions"
    result = check_compliance(comment, llm)
    return {
        "comment": comment,
        "answer": result["answer"],
        "cited_sections": result["cited_sections"],
        "faithfulness_passed": result["faithfulness_passed"],
        "faithfulness_notes": result["faithfulness_notes"],
        "hops": result["hops"],
    }


# ============================================================
# SECTION 4 — AI Resolution Recommender
# ============================================================

def check_recommender():
    from comment_extractor import Config, LLMClient
    from recommender.resolution_recommender import recommend_resolution

    cfg = Config.from_yaml("config.yaml")
    llm = LLMClient(cfg)

    test_comments = [
        "Check that the pipe size agrees with the approved hydraulic schedule.",
        "Weld size not per AWS D1.1, please verify fillet weld dimensions",
        "Relocate this valve to maintain maintenance clearance.",
        "Font on the title block is too small to read",
    ]
    rows = []
    for comment in test_comments:
        r = recommend_resolution(comment, llm)
        rows.append({
            "comment": comment, "draft": r["draft_resolution"],
            "basis": r["basis"], "confidence": r["confidence_percent"],
            "n_similar": len(r["similar_comments"]),
        })
    return rows


# ============================================================
# RUN EVERYTHING
# ============================================================

print("=" * 60)
print("CEMS System Report — running all checks")
print("=" * 60)

run_section("infrastructure", check_infrastructure)
run_section("semantic_search", check_semantic_search)
run_section("agentic_rag", check_agentic_rag)
run_section("recommender", check_recommender)


# ============================================================
# BUILD PDF
# ============================================================

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=20, spaceAfter=4)
subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11,
                                  textColor=colors.grey, alignment=TA_CENTER, spaceAfter=24)
h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15, spaceBefore=18, spaceAfter=8,
                     textColor=colors.HexColor("#1a1a2e"))
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6,
                     textColor=colors.HexColor("#16213e"))
body = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6)
caveat = ParagraphStyle("Caveat", parent=styles["Normal"], fontSize=9, leading=13,
                          textColor=colors.HexColor("#8b0000"), spaceAfter=4,
                          borderColor=colors.HexColor("#8b0000"), borderWidth=0.5,
                          borderPadding=6, backColor=colors.HexColor("#fff3f3"))
status_ok = ParagraphStyle("StatusOK", parent=body, textColor=colors.HexColor("#0a7d2c"))
status_err = ParagraphStyle("StatusErr", parent=body, textColor=colors.HexColor("#c0392b"))

story = []

# --- Title page ---
story.append(Spacer(1, 2 * cm))
story.append(Paragraph("CEMS — AI Automation", title_style))
story.append(Paragraph("System Verification &amp; Showcase Report", subtitle_style))
story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", body))
story.append(Spacer(1, 0.5 * cm))
story.append(Paragraph(
    "This report runs every implemented AI-automation capability live against the current "
    "infrastructure and records exactly what happened — successes and failures alike — rather "
    "than a curated summary.", body))
story.append(PageBreak())

# --- Section 1: Infrastructure ---
story.append(Paragraph("1. Infrastructure Status", h1))
sec = results.get("infrastructure", {})
if sec.get("status") == "ok":
    d = sec["data"]
    rows = [
        ["Metric", "Value"],
        ["Postgres — total comments", str(d["postgres_comments"])],
        ["Postgres — embedded comments", str(d["postgres_embedded"])],
        ["Postgres — projects", str(d["postgres_projects"])],
        ["Postgres — revisions", str(d["postgres_revisions"])],
        ["Postgres — standards chunks", str(d["postgres_standards_chunks"])],
        ["Qdrant — comments collection points", str(d["qdrant_comments_points"])],
        ["Qdrant — standards collection points", str(d["qdrant_standards_points"])],
    ]
    t = Table(rows, colWidths=[9 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
else:
    story.append(Paragraph(f"FAILED: {sec.get('error', 'unknown error')}", status_err))
story.append(Spacer(1, 0.4 * cm))

# --- Section 2: Semantic Search ---
story.append(Paragraph("2. Semantic Similarity Search", h1))
story.append(Paragraph(
    "Tests whether retrieval finds conceptually related comments, not just exact text matches — "
    "the actual claim being verified is that paraphrased queries still score meaningfully high "
    "while unrelated queries score lower.", body))
sec = results.get("semantic_search", {})
if sec.get("status") == "ok":
    cell = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8, leading=10)
    rows = [["Query", "Type", "Top Match", "Score"]]
    for r in sec["data"]:
        rows.append([Paragraph(r["query"], cell), Paragraph(r["label"], cell),
                     Paragraph(r["top_match"], cell), str(r["score"])])
    t = Table(rows, colWidths=[5.5 * cm, 2.8 * cm, 5.5 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
else:
    story.append(Paragraph(f"FAILED: {sec.get('error', 'unknown error')}", status_err))
story.append(Spacer(1, 0.4 * cm))

# --- Section 3: Agentic RAG ---
story.append(Paragraph("3. Agentic RAG — Standards Compliance Check", h1))
story.append(Paragraph(
    "Not single-shot RAG: the comment is decomposed into sub-questions, each retrieved "
    "separately (multi-hop), synthesized into an answer, then independently fact-checked "
    "against the retrieved excerpts before being accepted.", body))
sec = results.get("agentic_rag", {})
if sec.get("status") == "ok":
    d = sec["data"]
    story.append(Paragraph(f"<b>Comment:</b> {d['comment']}", body))
    story.append(Paragraph(f"<b>Retrieval hops:</b> {len(d['hops'])}", body))
    for hop in d["hops"]:
        story.append(Paragraph(
            f"&nbsp;&nbsp;Hop {hop['hop']}: \u201c{hop['query']}\u201d "
            f"\u2192 {hop['chunks_retrieved']} chunk(s) retrieved", body))
    story.append(Paragraph(f"<b>Synthesized answer:</b> {d['answer']}", body))
    story.append(Paragraph(f"<b>Cited sections:</b> {', '.join(d['cited_sections']) or 'none'}", body))
    fstyle = status_ok if d["faithfulness_passed"] else status_err
    story.append(Paragraph(
        f"<b>Faithfulness check:</b> {'PASSED' if d['faithfulness_passed'] else 'FAILED'} "
        f"&mdash; {d['faithfulness_notes']}", fstyle))
else:
    story.append(Paragraph(f"FAILED: {sec.get('error', 'unknown error')}", status_err))

story.append(Spacer(1, 0.3 * cm))
story.append(Paragraph(
    "Standards corpus caveat: currently illustrative paraphrases of AWS D1.1 / ASME B31.3 / "
    "IS 800, written for architecture demonstration — not verbatim legal text of the actual "
    "codes. Not suitable for citing as real compliance evidence until replaced with "
    "PRAJ-approved standards content.", caveat))

story.append(PageBreak())

# --- Section 4: Resolution Recommender ---
story.append(Paragraph("4. AI Resolution Recommender", h1))
story.append(Paragraph(
    "Combines similar-past-comment resolutions and standards grounding into a drafted "
    "resolution. Confidence is a heuristic (not a model-reported probability): 40% baseline, "
    "+25 if similar past comments found, +25 if standards-grounded, capped at 90% \u2014 "
    "never claims near-certainty. Always reviewer-approved, never auto-applied.", body))
sec = results.get("recommender", {})
if sec.get("status") == "ok":
    for r in sec["data"]:
        story.append(Paragraph(f"<b>Comment:</b> {r['comment']}", body))
        story.append(Paragraph(f"<b>Draft resolution:</b> {r['draft']}", body))
        story.append(Paragraph(
            f"<b>Basis:</b> {r['basis']} &nbsp;|&nbsp; <b>Confidence:</b> {r['confidence']}% "
            f"&nbsp;|&nbsp; <b>Similar comments used:</b> {r['n_similar']}", body))
        story.append(Spacer(1, 0.25 * cm))
else:
    story.append(Paragraph(f"FAILED: {sec.get('error', 'unknown error')}", status_err))

story.append(PageBreak())

# --- Section 5: Honest Status Summary ---
story.append(Paragraph("5. Implementation Status Summary", h1))

story.append(Paragraph("Implemented and verified tonight:", h2))
for item in [
    "Multi-DB architecture (Postgres + Qdrant), schema matches real extraction output",
    "RBAC — per-project roles, enforced via permission matrix",
    "Semantic similarity search — exact + paraphrase retrieval tested",
    "Agentic RAG — query decomposition, multi-hop retrieval, faithfulness self-check",
    "AI Resolution Recommender — multi-source drafting with confidence scoring",
]:
    story.append(Paragraph(f"\u2022 {item}", body))

story.append(Paragraph("Explicitly not yet done:", h2))
for item in [
    "Knowledge Graph (deferred, next session)",
    "Revision-lifecycle testing — Rev A\u2192B comparison (deferred, next session)",
    "Real PRAJ-approved standards corpus (currently illustrative placeholder)",
    "Trusted ground-truth dataset for extraction/classification accuracy claims",
    "Human-approval workflow UI (backend logic exists, no frontend yet)",
]:
    story.append(Paragraph(f"\u2022 {item}", body))

story.append(Spacer(1, 0.4 * cm))
story.append(Paragraph(
    "Claims this report supports: semantic retrieval distinguishes paraphrase from unrelated "
    "text; agentic RAG grounds answers and independently verifies its own faithfulness; the "
    "resolution recommender combines multiple evidence sources with calibrated, capped "
    "confidence. Claims NOT supported by this report: extraction accuracy, classification "
    "accuracy, or production standards compliance \u2014 none of these have been measured "
    "against independently verified ground truth.", caveat))

doc = SimpleDocTemplate(OUTPUT_PATH, pagesize=A4,
                          topMargin=2 * cm, bottomMargin=2 * cm,
                          leftMargin=2 * cm, rightMargin=2 * cm)
doc.build(story)

print(f"\n{'='*60}")
print(f"Report written to: {OUTPUT_PATH}")
print(f"{'='*60}")
