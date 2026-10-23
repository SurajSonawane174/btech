# CEMS Roadmap: from working prototype to a demonstrable, industry-ready product

Work in order. Each phase has an exit test. Do not start a phase before the previous exit test passes, except where marked parallel.

## Phase 0: Foundations (1-2 days)
- Move the repo to `C:\dev\cems` (no spaces, outside OneDrive). `git init`, commit with `.gitignore`.
- Package layout (`cems/extractor`, `db`, `vectordb`, `rag`, `recommender`, later `api`), `pyproject.toml`, `.env.example`, ruff + pre-commit.
- pytest with mock-based tests for behaviours already verified: UID parsing, ingest grouping, RAG success / no-requirement / hallucination-caught / synthesis-failed, recommender 3 confidence tiers.
- Full `docker-compose` (postgres, qdrant, healthchecks), schema via migrations (Alembic) instead of init-only SQL.
- `make up`, `make test`, `make demo` (runs `generate_system_report.py`).
**Exit:** fresh clone -> `make up && make demo` produces the PDF report.

## Phase 1: Data integrity and revisions (known issue 6.1)
- Metadata cascade in the current extractor: filename (with plausibility checks) -> PDF DocInfo -> title-block OCR/vision LLM -> manual override flag. Log which method resolved each field.
- Revision in the comment id, plus a revision-independent `position_key`. Ingest groups by `source_file`; exact insert counts via SELECT; idempotent re-ingest.
- Revision diff: link comments across revisions by `position_key` + text similarity + embedding similarity -> new / resolved / reopened / repeated; carry resolution history forward; status lifecycle.
**Exit:** a Rev A / Rev B fixture ingests as 2 revisions and the diff output is correct on every row.

## Phase 2: Evaluation harness (credibility, parallel with Phase 1 once data exists)
- Gold dataset: anonymized real drawings from PRAJ if possible; otherwise hand-annotate real public drawings with 2 annotators and report Cohen's kappa. Record provenance.
- Port `eval_metrics.py` / `ablation_study.py` to the current schema. Measure: extraction P/R/F1 and field accuracy (page, author, date, text), metadata accuracy per method, classification P/R/F1 per class (Gemma vs rule-based separately), duplicate detection with threshold sweep (fuzzy vs embedding), retrieval hit@1/hit@3/MRR, RAG citation accuracy and faithfulness (human-checked sample), recommender human rating (relevance, actionability, safety, 1-5, at least 50 items).
- Ablations: dedup on/off, LLM vs rules, vision fallback on/off, RAG on/off.
**Exit:** `make eval` prints a metrics table with dataset provenance. Only these numbers go into the paper/PPT.

Free win before real data exists: write 15-20 paraphrases of ingested comments and report retrieval hit@1/hit@3, labelled "synthetic set".

## Phase 3: AI automation depth (the differentiators; priority order)
1. Learning loop: store approve / edit / reject on every suggestion, track acceptance rate, feed accepted edits back as few-shot examples.
2. Hybrid retrieval (keyword + dense) with a reranker and project/discipline filters.
3. Production LLM layer: JSON-schema validated outputs, retries with backoff, response caching, prompt versioning, per-call cost and latency logging, provider switch OpenRouter <-> local Ollama model (on-prem mode).
4. Semantic duplicate detection (embedding + fuzzy), threshold tuned on the gold set.
5. Entity extraction (equipment tags, line numbers, spec refs) -> fill `entities` / `comment_entity_edges` -> graph queries ("all open comments on P-102 across revisions"). Postgres first, Neo4j only if needed.
6. "Ask CEMS": natural-language query over the comment database (text-to-filter + RAG) with citations.
7. Priority/severity scoring, discipline classification beyond technical/aesthetic, HDBSCAN clustering with LLM-generated labels, assignment suggestions.
8. Review-completeness detector: topics that similar past drawings always got comments on but this one did not.
9. Real standards: only PRAJ-provided or licensed text, ingested with clause metadata and version; keep the faithfulness gate.
**Exit:** each item ships with a metric from Phase 2, not just a demo.

## Phase 4: Product surface (coordinate with the teammate who owns backend/RBAC)
- FastAPI endpoints: upload PDF, job status, list/filter comments, similar comments, recommend, approve/edit/reject, revision diff. Async jobs for PDF processing. JWT + the teammate's RBAC. Audit log (who, when, model, prompt version, sources, final text).
- React review UI: PDF page with snapshot, AI suggestion panel (basis, similar comments, standards references with a faithfulness badge, "illustrative standards" label), revision diff view, dashboard (closure time, category mix, repeated issues), Excel/CSV export, webhook stub for Jira/Autodesk Construction Cloud.
**Exit:** the full demo storyline runs from a browser.

## Phase 5: Production readiness
- Postgres RLS + RBAC tests; secrets management; redact proprietary values before any external LLM call; on-prem mode documented.
- Structured logs, metrics, tracing; backups; load test on a large batch (for example 1,000 pages); dependency and OWASP checks; CI running tests and `make eval`.
- Docs: README, architecture, API, runbook, limitations / model card.

## Phase 6: Demo and report
- 8-minute demo: upload PDF -> extraction with snapshots -> duplicates flagged -> classification -> similar past comments -> AI suggestion with citations -> approve/edit -> audit trail -> Rev A/B diff -> dashboard.
- Failure demos: LLM outage falls back cleanly; real-LLM hallucination caught by the faithfulness check.
- Timed manual-vs-CEMS study (several reviewers, same drawings) before claiming any time saving.
- Update paper and PPT with measured numbers only; fix `Fig. ??a`, the workflow figure and the duplicate impact slide; the paper names Gemini 3.5 Flash while the pipeline now uses `google/gemma-4-31b-it` via OpenRouter.

## What industry will ask (have an answer ready)
Data confidentiality (on-prem mode, redaction); audit trail and sign-off; measured accuracy with a named dataset; integration with their tracker; scale and speed; scanned and handwritten drawings; standards licensing and versioning; role-based access.
