# CEMS — Comment Extraction & Management System

BTech final-year project, COEP Technological University Pune (CSE). Guide: Dr. Vahida Z. Attar. Industry partner: PRAJ.
Pipeline: annotated engineering-drawing PDFs -> structured, traceable review records -> AI layer (semantic search, standards-grounded agentic RAG, AI-drafted resolutions with human approval).

**Repo/AI-scope owner:** Yash Shah. Teammates own login/roles (Express backend, `users.role`), the backend routes and the frontend. Integrate with their interfaces; do not re-implement them.
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
| `database/schema.sql`, `database/db.py` | FINAL schema, exactly 3 tables: `documents` (one row per revision, unique on `unique_doc_revision`), `users`, `comments` (incl. `embedded`, `ai_suggested_resolution`, `ai_confidence_percent`, `resolution_text`, `resolved_at`). bigint ids. No RBAC, standards or trace tables |
| `vectordb/qdrant_client.py`, `vectordb/embedder.py`, `vectordb/comment_sync.py` | Qdrant collections `comments` (point id = `comments.id`) and `standards_chunks` (integer ids), 768-d cosine; Ollama `nomic-embed-text`; embedding sync, similar search, resolve/reopen payload updates |
| `ingest.py` | CSV -> `documents` + `comments` (explicit allowlist, `--project --supplier --po` required) -> embedding sync |
| `cems_cli.py` | JSON CLI the Express backend calls: ingest, embed-sync, search, suggest, resolve, reopen, seed-standards, rebuild-vectors |
| `standards_corpus/seed_standards.py` | PLACEHOLDER standards (AWS D1.1, ASME B31.3, IS 800): illustrative paraphrases, not real code text. Qdrant only |
| `agentic_rag/compliance_check.py` | decompose -> multi-hop retrieve -> synthesize -> faithfulness check; trace returned in the result + Python log (no DB table) |
| `recommender/resolution_recommender.py` | resolved similar comments + verified standards -> draft; `suggest_resolution` stores only `ai_suggested_resolution` / `ai_confidence_percent` |
| `scripts/demo_pipeline.py` | Reproducible synthetic end-to-end demo (real extractor/ingest/Postgres/Qdrant; mock LLM + hash embeddings by default, labelled) |
| `scripts/ocr_smoke_test.py` | Opt-in real LightOnOCR check on one synthetic box (`--confirm-download`, ~2 GB) |
| `config_utils.py` | `parse_bool` for config (invalid -> error), `strict_true` for model output (fail closed) |
| `generate_system_report.py` | Live checks with computed gates (PASS/FAIL/ERROR/NOT_CONFIGURED/NO_DATA) -> PDF + JSON; exit 0 only if all pass. `--target demo`, `--junit`, `--evaluation` |
| `scripts/live_smoke.py` | Per-service real checks (Postgres, Qdrant temp collection, Ollama, LLM JSON); never falls back to mocks |
| `evaluation/` | Ground-truth format, metrics, `run_evaluation.py` (`--kind synthetic` or `real`), `synthetic_eval.py`. No real labelled data yet |

## Commands (Windows / PowerShell, venv active)
```
docker compose up -d                      # postgres + qdrant (Ollama runs natively; container only with --profile ollama)
ollama pull nomic-embed-text
python comment_extractor.py --dry-run     # no LLM calls: native annots / empty pages / colour boxes per PDF
python comment_extractor.py --input input   # add --max-pages 2 for a smoke test
python -m pytest -q tests
python cems_cli.py ingest --input output/master_comments.csv --project P-1001 --supplier "ACME" --po PO-4512
python cems_cli.py seed-standards
python cems_cli.py rebuild-vectors --confirm   # once, after moving to integer Qdrant ids
python scripts/live_smoke.py              # which real services work (add --pg-temp-db with CEMS_TEST_DATABASE_URL)
python evaluation/synthetic_eval.py       # harness sanity check (synthetic only)
python generate_system_report.py          # -> CEMS_System_Report_<timestamp>.pdf/.json (exit 1 unless all gates pass)
```

## Contracts
- `Config.from_yaml(Path("config.yaml"))`, `LLMClient(cfg).chat_json(system, user) -> dict`
- Final schema: 3 tables only (`documents`, `users`, `comments`), bigint ids, status `open` / `closed`. Never reference projects, revisions, resolutions, standards or trace tables, ENUM types or UUIDs.
- `check_compliance(comment_text, llm, comment_id=None)` -> `verified` (True only if retrieval, synthesis, code-side citation validation and a strictly parsed faithfulness check all pass), `evidence_status`, `cited_sections`/`cited_chunk_ids` (derived from validated `[S#]` tags, never copied from the model), `retrieved_chunk_ids`, `evidence`, `citation_check`, `faithfulness_passed`, `faithfulness_notes`, `hops`, `corpus_status`, `answer`, `trace`
- `recommend_resolution(comment_text, llm, praj_project_number=None, comment_id=None, top_k_similar=3, exclude_same_document=True, cross_project=False, min_similarity=0.55)` -> always a draft (`stored_text` = draft + "Referenced standards: ...", `citations`, `faithfulness_failed`, `trace`); `status`, `requires_human_approval=True`, `auto_applied=False`, `draft_resolution`, computed `basis` (+ `model_claimed_basis`), `similar_comments` (closed comments with an approved `resolution_text`), `standards_evidence` (verified only), `standards_grounding`, `corpus_status`, `confidence_percent` (heuristic) + `confidence_rationale`, `uncertainty`, `retrieval_scope`
- Qdrant point id = Postgres `comments.id` (bigint). Standards point ids = stable positive 63-bit integers. Embedding dim 768.
- Comment id: `PROJECT-DRAWING-REV-page-row-seq-HASH12` (<= 100 chars; seq is per page; HASH12 = first 12 hex of `source_file_sha256`). Duplicates are detected on `source_file_sha256`, never on `comment_id`.
- Native annotation rects are stored in DISPLAY (rotated) coordinates; `get_text(clip=)` needs unrotated ones (`* page.derotation_matrix`), `get_pixmap(clip=)` needs display ones.
- Per-PDF output folder: `output/<stem>/`, or `output/<stem>__<sha8>/` when two inputs share a basename in one run. `run_status.json` in each folder says ok/failed.
- Ingest groups by source file; a missing revision is stored as `NA`; an unresolved drawing is skipped unless `--allow-unresolved`; a second file claiming an existing revision, or the same PDF under another supplier/PO, is a conflict, not a merge.

## Hard rules
1. Never claim extraction or classification accuracy without trusted ground truth. "Native annotation coverage" is not accuracy. Do not repeat the old 95-98% / ~99% claims.
2. The standards corpus is placeholder. Label it "illustrative" in every demo, report and UI.
3. AI never auto-resolves a comment: suggestion (`ai_suggested_resolution`) -> human approve/edit -> `resolution_text`, `resolved_at`, status `closed`.
4. A failed LLM call or failed synthesis must never be reported as verified. Keep the `synthesis_succeeded` gate before the faithfulness check.
5. Booleans from config go through `parse_bool`; booleans from a model go through `strict_true`. Never use plain truthiness.
6. `cursor.rowcount` after `execute_values ... ON CONFLICT DO NOTHING` is unreliable. Count with a SELECT.
7. Cast id lists: `WHERE id = ANY(%s::bigint[])`.
8. No secrets in code, logs, commits or screenshots.
9. Logic changes need a mock-based test; behaviour changes also need a live run of `generate_system_report.py`.
10. `comment_extractor.py` is ~1200 lines and works. Ask before large refactors of it; make small, reviewable commits.

## Environment gotchas
- Original folder `C:\Users\yashr\OneDrive\Desktop\btech_ new` contains a space and sits inside OneDrive. Work from a path like `C:\dev\cems` instead (spaces break quoting; OneDrive sync can corrupt `.venv`, `.git` and Docker volumes).
- Python 3.13, Windows 11, PowerShell. Multi-line Python pasted into PowerShell fails: use `.py` files or `python -c "..."`.
- Ollama is native on Windows. If `ollama` is not found: `$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"`.
- Qdrant client 1.19.x vs server 1.12.4 prints a compatibility warning (works); align versions when convenient.
- User has limited mobile data and low C: space (Docker disk image was moved to D:). Avoid large downloads and say how big one is before suggesting it.
- OpenRouter model is `google/gemma-4-31b-it` (the `:free` variant was rate-limited with 429s).
