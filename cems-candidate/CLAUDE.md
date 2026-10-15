# CEMS — Comment Extraction & Management System

BTech final-year project, COEP Technological University Pune (CSE). Guide: Dr. Vahida Z. Attar. Industry partner: PRAJ.
Pipeline: annotated engineering-drawing PDFs -> structured, traceable review records -> AI layer (semantic search, standards-grounded agentic RAG, AI-drafted resolutions with human approval).

**Repo/AI-scope owner:** Yash Shah. Teammates own RBAC and the multi-DB/backend/frontend. Integrate with their interfaces; do not re-implement them.
**Goal:** an industry-ready, demonstrable product that PRAJ will see live. Prefer correctness, evidence and auditability over feature count.

Read first, every session: `docs/HANDOFF.md` (state, history, bugs already fixed) and `docs/ROADMAP.md` (what to build, in order).

## Repo map
| Path | Purpose |
|---|---|
| `comment_extractor.py` | PDF -> comments. Native PyMuPDF annotations first; for pages with none: colour-box detection read by hosted vision LLM or local OCR (`vision.box_reader`), then optional whole-page OCR (fails closed to review); optional snapshot enrichment (`is_handwritten`, `visual_feature`); rule-based or LLM classification; RapidFuzz duplicates; snapshots. Writes `output/<pdf>/final_output.csv` and `output/master_comments.csv`. Holds `Config` and `LLMClient`: reuse them, never add a second LLM wrapper |
| `local_ocr.py` | Optional on-prem OCR (LightOnOCR-2-1B). Lazy imports: the pipeline runs without torch when `ocr.enabled: false`. Reads detected box crops (`ocr_rect`) or whole pages (`ocr_page_lines`) |
| `config.colab.yaml`, `colab_run.ipynb` | GPU run on Colab: same extractor, `vision.box_reader: local_ocr`, full-page OCR on. Outputs are ingested on the laptop |
| `tests/` | pytest, mock-based (fake LLM + fake OCR + synthetic PDFs). Run before every commit |
| `config.yaml`, `.env` | Settings / secrets (`OPENROUTER_API_KEY`, Postgres, Qdrant, Ollama). `.env` is never committed |
| `database/schema.sql`, `database/db.py` | Postgres schema (columns mirror extractor `COLUMNS`), RBAC (`db.can`), entities + edges (graph, not populated yet), resolutions, standards, `rag_query_traces` |
| `vectordb/qdrant_client.py`, `vectordb/embedder.py` | Qdrant collections `comments` and `standards_chunks` (768-d, cosine); Ollama `nomic-embed-text` |
| `ingest.py` | CSV -> Postgres -> embeddings -> Qdrant |
| `standards_corpus/seed_standards.py` | PLACEHOLDER standards (AWS D1.1, ASME B31.3, IS 800): illustrative paraphrases, not real code text |
| `agentic_rag/compliance_check.py` | decompose -> multi-hop retrieve -> synthesize -> faithfulness check -> trace log |
| `recommender/resolution_recommender.py` | similar past comments + verified standards grounding -> drafted resolution, never auto-applied |
| `generate_system_report.py` | Runs every check live and writes one PDF. Use it as the regression check and the demo artifact |

## Commands (Windows / PowerShell, venv active)
```
docker compose up -d                      # postgres + qdrant (Ollama runs natively on the host, not in compose)
ollama pull nomic-embed-text
python comment_extractor.py --dry-run     # no LLM calls: native annots / empty pages / colour boxes per PDF
python comment_extractor.py --input input   # add --max-pages 2 for a smoke test
python -m pytest -q tests
python ingest.py --input output/master_comments.csv
python standards_corpus/seed_standards.py
python generate_system_report.py          # -> CEMS_System_Report_<timestamp>.pdf
```

## Contracts
- `Config.from_yaml(Path("config.yaml"))`, `LLMClient(cfg).chat_json(system, user) -> dict`
- `check_compliance(comment_text, llm, comment_id=None) -> {answer, cited_sections, faithfulness_passed (True/False/None), faithfulness_notes, hops, cited_chunk_ids}`
- `recommend_resolution(comment_text, llm, project_id=None, comment_id=None, top_k_similar=3) -> {draft_resolution, basis, similar_comments, standards_grounding, confidence_percent}`
- Qdrant point id = Postgres `comments.id` (UUID). Embedding dim 768.
- Comment id format from the extractor: `PROJECT-DRAWING-page-row-seq` (no revision in it: see known issues).

## Hard rules
1. Never claim extraction or classification accuracy without trusted ground truth. "Native annotation coverage" is not accuracy. Do not repeat the old 95-98% / ~99% claims.
2. The standards corpus is placeholder. Label it "illustrative" in every demo, report and UI.
3. AI never auto-resolves a comment: suggestion -> human approve/edit/reject -> audit record (who, when, model, sources).
4. A failed LLM call or failed synthesis must never be reported as verified. Keep the `synthesis_succeeded` gate before the faithfulness check.
5. `cursor.rowcount` after `execute_values ... ON CONFLICT DO NOTHING` is unreliable. Count with a SELECT.
6. Cast UUID lists: `WHERE id = ANY(%s::uuid[])`.
7. No secrets in code, logs, commits or screenshots.
8. Logic changes need a mock-based test; behaviour changes also need a live run of `generate_system_report.py`.
9. `comment_extractor.py` is ~1200 lines and works. Ask before large refactors of it; make small, reviewable commits.

## Environment gotchas
- Original folder `C:\Users\yashr\OneDrive\Desktop\btech_ new` contains a space and sits inside OneDrive. Work from a path like `C:\dev\cems` instead (spaces break quoting; OneDrive sync can corrupt `.venv`, `.git` and Docker volumes).
- Python 3.13, Windows 11, PowerShell. Multi-line Python pasted into PowerShell fails: use `.py` files or `python -c "..."`.
- Ollama is native on Windows. If `ollama` is not found: `$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"`.
- Qdrant client 1.19.x vs server 1.12.4 prints a compatibility warning (works); align versions when convenient.
- User has limited mobile data and low C: space (Docker disk image was moved to D:). Avoid large downloads and say how big one is before suggesting it.
- OpenRouter model is `google/gemma-4-31b-it` (the `:free` variant was rate-limited with 429s).
