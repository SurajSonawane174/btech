# CEMS Handoff: state, history, decisions

Written when the project moved to a new account (Claude Code). Everything here comes from the working sessions; where something was only tested with mocks, it says so.

## 1. Who asked for what

**PRAJ (via the guide):** (1) RBAC, (2) multi-database, (3) automate the system with AI, plus new novelties. **Guide (Dr. Attar):** test on a trusted dataset (otherwise results have no significance), go for full AI automation.

**Review points on the earlier paper (13), and where each stands**
| # | Point | Status |
|---|---|---|
| 1 | Larger, independently labeled dataset (27 drawings / 142 comments is too small) | OPEN. Needs PRAJ data or a self-built gold set with 2 annotators and Cohen's kappa |
| 2 | Precision/Recall/F1 for extraction, duplicates, classification | Scripts exist in the legacy folder (`eval_metrics.py`); must be ported to the current schema (`classification_method`, not `classification_source`) |
| 3 | Quantitative duplicate-detection evaluation, FP/FN cases | Same script covers it; threshold sweep is a TODO |
| 4 | Gemini vs rule-based fallback evaluated separately | Current extractor logs `classification_method`; evaluation not rerun |
| 5 | Metadata success only 43.66% | Cascade (filename with plausibility checks -> PDF DocInfo -> title-block OCR) was built in the LEGACY `doc_process.py` only. Current extractor still uses filename-only metadata, so the problem is live (see 6.1) |
| 6 | Controlled comparison with the manual process | OPEN. Needs a timed study |
| 7 | Ablation study | `ablation_study.py` (legacy) exists; port and run on a real gold set |
| 8 | Reproducibility parameters (model, prompt, threshold, rules) | Drafted in `PAPER_ADDITIONS.md` (legacy folder); model/provider have changed since, update it |
| 9 | Revision-level traceability of comment IDs | Fix designed and built in legacy (revision in UID + separate `position_key` for cross-revision matching); NOT in the current extractor |
| 10 | Security/privacy (external LLM, no RLS) | `rls_policies.sql` (legacy) and per-project RBAC in `schema.sql`; privacy text drafted |
| 11 | Grammar/typos in the manuscript | OPEN, needs the manuscript text |
| 12 | Comparison with commercial/research systems | Drafted in `PAPER_ADDITIONS.md` |
| 13 | Failure-case analysis | Template only; fill from real eval output |

## 2. Codebase lineage
1. **Legacy `btech/`** (`doc_process.py`): direct Gemini SDK, Tesseract OCR fallback, one API call per comment. It hit the free-tier limit of 15 requests/minute on a 239-comment file, and `gemini-2.0-flash-lite` was retired (404). That explains part of the paper's 47.89% fallback rate. A "showcase" patch set added `classification_source`, the metadata cascade, revision-safe UIDs, `eval_metrics.py`, `ablation_study.py`, `rls_policies.sql`, `local_vlm_classifier.py` (Ollama qwen3-vl), `glm_ocr_titleblock.py`.
2. **Current `btech_ new/`** (`comment_extractor.py`): OpenRouter-compatible `LLMClient`, batched classification per page, `--dry-run`, hue-clustered colour-box detection feeding a vision-LLM fallback, separates "extraction crashed" from "page has no comments". **This is the canonical pipeline.** The AI layer (everything outside the extractor) was built against its `COLUMNS` schema.

## 3. Architecture
```
PDF -> comment_extractor.py -> output/*.csv (+snapshots)
        -> ingest.py -> Postgres (documents, users, comments; final 3-table schema)
                     -> Ollama embed -> Qdrant: comments
standards (placeholder) -> embed -> Qdrant: standards_chunks
comment -> compliance_check (decompose -> multi-hop -> synthesize -> faithfulness) -> trace
comment -> recommender (closed similar comments + verified standards) -> ai_suggested_resolution -> human approval -> resolution_text
```
Not built: API, frontend, approval UI, knowledge graph population, revision diff.

## 4. What works, with the evidence
| Capability | Evidence | Caveat |
|---|---|---|
| Extraction of native annotations | 5 synthetic PDFs x 10 pages -> 250 rows, 0 vision-fallback pages, 0 extraction errors | Synthetic, no ground truth: coverage, not accuracy |
| Ingest + embeddings | 50/50 comments embedded in Postgres and Qdrant | 250 rows collapsed to 50 (see 6.1) |
| Semantic search | exact query 1.0; paraphrase 0.9325; valve/maintenance 0.8528; flow-direction 0.8436; nozzle 0.8845 | Similarity score is not accuracy. 50 synthetic comments |
| Agentic RAG, success path | weld/AWS D1.1 comment: 2 hops, 3 chunks each, correct citation (Clause 2.4), faithfulness passed with reason | Placeholder standards |
| Agentic RAG, failure handling | Hallucinated citation caught (`passed: False`) in a MOCKED test; LLM-failure path verified live (429) after the fix in section 5 | Hallucination catch not yet reproduced with the real LLM |
| Recommender | Paraphrase matched stored resolution at 0.9354; draft generated; basis `similar_comments`, confidence 65 | One synthetic resolution only. Confidence is a capped heuristic (40 base, +25 similar, +25 verified standards, max 90), not a probability |
| LLM access | `google/gemma-4-31b-it` returned 200 | `:free` variant 429s |
| Older paper numbers | 7.59x parallel speedup (255.18 s -> 33.63 s, 11 workers); metadata 43.66%; fallback 47.89%; classification 90/91; duplicates P 0.962 / R 1.0 / F1 0.981 at threshold 90 | All on 27 internally created PDFs with self-made labels (2 aesthetic examples only). Not evidence of generalization |

## 5. Bugs found and fixed (do not regress)
- psycopg2 UUID arrays: `ANY(%s::uuid[])` in `mark_comments_embedded`, `mark_standards_chunks_embedded`, `get_resolution_history_for`.
- `insert_resolution` called `fetchone()` after an UPDATE; now captures the id first.
- A failed synthesis returned an error string that the faithfulness checker then "verified". Added `synthesis_succeeded`; when False the faithfulness check is skipped and `faithfulness_passed=False`.
- Ingest reported `comments=1` from `rowcount` with `ON CONFLICT DO NOTHING`; real count came from SELECT.
- OpenRouter `:free` model 429 -> switched both model fields in `config.yaml` to the paid ID.
- Ollama on Windows: broken `manifests-v2` symlink for `nomic-embed-text` repaired by replacing it with a plain file copy.

## 6. Known issues
1. **Metadata/UID collision (highest priority).** `CEMS_Engineering_Annotation_Set_N.pdf` parses to drawing=`Annotation`, revision=`Set` for all five files. `UNIQUE(revision_id, comment_uid)` + `ON CONFLICT DO NOTHING` then silently drops comments from files 2-5. Fix: group by `source_file` (the master CSV has it), validate filename parts, add the metadata cascade, put revision in the UID plus a revision-independent `position_key`.
2. No revision lifecycle or diff yet (can't test Rev A -> Rev B until 6.1 is fixed).
3. No knowledge graph: the final schema has no entity tables.
4. The API/UI live in the Express backend; this engine exposes `cems_cli.py`. RAG traces are returned and logged, not stored.
5. Debt: `import fitz` deprecation (use `pymupdf`); Qdrant client/server mismatch; `embedder.check_ready()` false negative (embedding calls work); no automated test suite.
6. Cost: compliance check = 3-4 LLM calls, recommendation = up to 4. Needs batching, caching and per-call cost logging before scale.
7. Standards licensing: real ISO/ASME/AWS/IS text is copyrighted. Use PRAJ-provided internal procedures or licensed excerpts.

## 7. Claims policy
**May claim:** semantic retrieval separates paraphrases from unrelated text; the RAG pipeline decomposes, retrieves, synthesizes and independently checks faithfulness, with explicit failure handling; the recommender combines history and verified standards into a reviewer-facing draft with a capped heuristic confidence; extraction covers native annotations on the synthetic set.
**May not claim (yet):** extraction/classification accuracy, production standards compliance, validated recommendation quality, knowledge graph, integrated UI/backend, any labor-saving number.

## 8. Decisions
- Qdrant + Ollama + Postgres chosen by Yash (production-like, local embeddings with no API cost or rate limits).
- Ollama native on Windows because the Docker image (~3.8 GB) exceeded the available mobile data.
- Placeholder standards kept for the demo; real standards deferred.
- Knowledge graph and revision tracking explicitly deferred to the next phase (now Phase 1 and Phase 3 in `ROADMAP.md`).
- A real Gemini API key from the legacy `.env` was pasted into a chat once. Confirm it was revoked. Never commit `.env`.

## 9. Open questions for Yash
- Can PRAJ share anonymized real reviewed drawings (with the reviewer comments and resolutions)? Their domain standards or internal procedures?
- Which backend/RBAC interfaces does the teammate expose, and what is the timeline?
- Demo date for PRAJ, and is the demo on a laptop or a hosted environment?
- Is an on-prem/local-LLM mode a requirement for PRAJ's confidentiality rules?

## 10. Extractor merge with the teammate's Colab notebook (2026-10-15)
Base kept: `comment_extractor.py` (canonical, schema-aligned). Taken from the notebook:
- LightOnOCR-2-1B local OCR -> `local_ocr.py`. Used two ways: (a) on detected box crops, as an on-prem
  alternative to the hosted vision reader (`vision.box_reader: local_ocr`); (b) whole-page, last resort.
- Empty-reply / no-choices detection (`LLMClient._content`), now on every call path.
- Snapshot vision pass -> `enrichment` (is_handwritten, visual_feature). New column `visual_feature`
  (schema + `database/migrations/001_visual_feature.sql` for existing DBs).
- `--max-pages` smoke-test flag; Colab runner (`colab_run.ipynb`, `config.colab.yaml`).
Changed on the way in (deliberately):
- Whole-page OCR fails closed: if the LLM filter fails or is off, lines go to `review_candidates`
  (+ transcript file), never into comments. The notebook kept all lines on failure.
- Enrichment never overrides the classifier's category and its self-reported confidence is dropped.
- OCR rows get no `extraction_confidence_percent` (blank) until Phase 2 measures them.
- Retry loop fixed: attempts = 1 + max_retries, no sleep after the last, no `raise None`.
- LLM client only created when an enabled feature needs it: an all-local run needs no API key.
Rejected: `stealth/space-bunny-alpha` model (stealth OpenRouter models are temporary and typically log
prompts: not acceptable for PRAJ drawings); unpinned git transformers in the main requirements; Colab-only
code paths inside the extractor.
Verified: 18 mock tests; CLI end-to-end on synthetic PDFs with no API key. NOT verified: the real
LightOnOCR model (Hugging Face unreachable from the build sandbox). First live check: run `colab_run.ipynb`.

## 11. Chunk A: extraction reliability and ingest integrity (2026-10-15)
- C5: same-basename PDFs in one run no longer overwrite each other (before: 2 files x 3 comments -> 3 master rows).
  Folder `<stem>__<sha8>` only on collision; master CSV gains `source_path`, `output_dir`; per-file summary keyed by path.
  Each run clears only the extractor's own files first and writes `run_status.json`, so a failed rerun cannot leave a
  stale `comments.json`.
- C6: revision rule tightened (PID/GA/RAW/REV/AA rejected; 0, A1, RA, REV-B, P1 accepted). Title-block LLM values are
  validated like every other source; null-like answers ignored, implausible ones rejected, filename conflicts recorded
  in the new `metadata_notes` column.
- Rotation: `annot.rect` is unrotated, page.rect / pixmaps are display coordinates. Before the fix, on 90/180/270
  pages the snapshot crop missed the annotation, and row/position_key were wrong; the title-block clip read the wrong
  corner. Tests now compare against the annotation's rendered pixels at 0/90/180/270.
- Ingest: "NA" kept as text (before: revision "NA" rows were silently dropped by groupby, comment text "NA" became
  NaN); grouping by source_file_sha256; unresolved metadata skipped unless --allow-unresolved; conflicts reported;
  insert counts from SELECTs (before: always 1). Verified on a real PostgreSQL 16 (tests/test_ingest_pg.py).
- Not changed: schema.sql (position_key / provenance columns are not stored in Postgres yet), PRAJ backend.

## 12. Chunk B: AI reliability (2026-10-16)
Fixed (each with a regression test that fails on the previous code):
- Booleans: config values parsed with `parse_bool` (quoted "false" was truthy; garbage now stops the run with the
  key name); model verdicts parsed with `strict_true` (the faithfulness verdict "false" was reported as PASSED).
- RAG evidence is validated in code: excerpts are tagged [S#]; citations to tags never shown, and clause/section
  numbers in the answer that appear in no retrieved excerpt, give `citation_invalid`; no citation or a model-declared
  lack of evidence gives `insufficient_evidence`. `verified` requires every gate. `cited_chunk_ids` now really are
  the cited chunks. Same-clause duplicates are merged (ids kept), distinct clauses kept. Qdrant/embedder failures
  return `retrieval_failed` instead of raising.
- Recommender: never matches the comment itself (id excluded inside Qdrant and re-checked), excludes the comment's
  own revision, scoped to its project unless `cross_project=True`; history uses the NEWEST HUMAN resolution
  (it used the oldest, and included unreviewed AI drafts); basis computed from evidence; output is always a draft
  with `requires_human_approval=True`; uncertainty listed; illustrative corpus gives +10 not +25.
- DB: `insert_resolution(source='ai_suggested')` no longer resolves the comment; standards seeding idempotent;
  `log_rag_trace` cast to uuid[] (EVERY trace insert used to fail silently); `get_comment_context` added.
- Embedder: lazy ollama import (the AI layer could not be imported without ollama), check_ready reads new-style
  listings, no zero vectors. Extractor: classification accepts only its own batch ids; `duplicate_of` column.
- Qdrant payload gains document_id / comment_uid; search results return provenance.
Verified here: 159 passed + 6 skipped without services; 165 passed with a real PostgreSQL 16 (in-memory Qdrant for the
Qdrant tests; also run on qdrant-client 1.19.1). Demo: scripts/demo_pipeline.py (mock LLM, hash embeddings).
NOT verified: real LLM behaviour, real nomic-embed-text retrieval quality, Qdrant server, LightOnOCR (needs
scripts/ocr_smoke_test.py on a GPU). requirements.txt pins qdrant-client==1.12.4, which does not exist on PyPI (fix in D).

## 13. Reliability and evaluation batch (2026-10-17)
- PDF reply threads: annotations with /IRT used to become separate client comments (a PRAJ reply
  "Agreed, will revise" was stored as a client comment). `link_replies()` now attaches a reply whose chain reaches
  an extracted root to that root (`reply_count`, `replies_json`; review-status replies keep their `state`).
  Unlinkable replies are KEPT as comments with `reply_link_status` = parent_missing / malformed_reference / cycle;
  a status-only reply with no text that cannot be linked is dropped and counted (`run_status.json` -> reply_threads).
  Switch: `extraction.link_replies` (default true; false = previous behaviour). Side effect: per-page sequence
  numbers in comment ids shift on pages that had replies. Three CSV columns appended; ingest ignores them.
- `generate_system_report.py` rewritten: statuses are computed per check (PASS / FAIL / ERROR / NOT_CONFIGURED /
  NO_DATA), the verdict is "ALL LIVE CHECKS PASSED" only if every gate passes (exit 0, else 1). Removed the
  hard-coded "Implemented and verified tonight" list, including the false RBAC claim. Paths are relative to the
  script, `--target demo` reads `cems_demo` + demo collections, queries match the current demo texts, `--junit`
  and `--evaluation` add test and metric evidence. Read-only except normal rag_query_traces audit rows.
- `scripts/demo_pipeline.py --qdrant server` DELETED the team collections `comments` / `standards_chunks`. It now
  uses only `cems_demo_comments` / `cems_demo_standards_chunks`; collection names are env-overridable
  (QDRANT_COMMENTS_COLLECTION / QDRANT_STANDARDS_COLLECTION). It refuses to drop an existing `cems_demo` unless
  `--recreate-demo-db`, and never `cems` / `postgres`.
- `evaluation/`: metrics (extraction P/R/F1 with one-to-one fuzzy matching, classification accuracy + macro-F1,
  duplicate pair P/R/F1, retrieval P/R/hit@k), gold CSV format + empty templates, `run_evaluation.py` (mandatory
  --kind synthetic|real), `synthetic_eval.py`. No real labelled dataset exists: real-world metrics are unavailable.
  Synthetic run (7 comments, rule-based classifier): extraction P=R=1.0, duplicates P=R=1.0, classification
  accuracy 0.71 / macro-F1 0.51 -- synthetic only, not a quality claim.
- `scripts/live_smoke.py`: Postgres (read-only schema check; optional temporary `cems_smoke_*` database with
  `--pg-temp-db`), Qdrant (temporary `cems_smoke_*` collection, existing collections compared before/after),
  Ollama embedding, LLM JSON. PASS / FAIL / SKIPPED / NOT_CONFIGURED, passwords masked, no mock fallback.
- docker-compose: the `ollama` service is behind the `ollama` profile (clashed with native Ollama on 11434).
- `database/migrations/001_comment_provenance_columns.sql`: PROPOSED, additive, nullable, idempotent; not applied
  and not yet written by ingest.
Verified here: 228 passed with real PostgreSQL 16 (216 passed + 12 skipped without it), qdrant-client 1.12.1.
Real services exercised in this sandbox: PostgreSQL 16.15; Qdrant SERVER 1.12.4 (live_smoke round trip, demo in
server mode with a pre-existing team collection left intact, report infrastructure gate PASS on `cems_demo`).
NOT verified: Ollama embeddings, OpenRouter LLM (no key here), LightOnOCR, real PRAJ PDFs (incl. Acrobat-made
reply threads), real-world accuracy.

## 14. Final database schema refactor (2026-10-29)
The live database is final: exactly 3 tables (`documents`, `users`, `comments`), bigint ids, no ENUMs,
no UUIDs. Everything that used the older 12-table draft was rewritten; earlier sections of this file
describe that older design as history.
- `database/schema.sql` reproduces the final schema exactly (incl. `unique_doc_revision`).
- `database/db.py`: document upsert on `unique_doc_revision` (missing revision stored as `NA`; customer
  `NA` -> NULL, as the team's SQL did), comments with `ON CONFLICT (comment_id)`, AI draft / resolve /
  reopen functions. Status values `open` / `closed`. Removed: projects, memberships, RBAC `can()`,
  revisions, entities, resolutions, standards tables, `log_rag_trace`.
- `ingest.py`: `--project --supplier --po` required; explicit allowlist mapping (sr_no, email,
  annotation_type, classification_method, comment_source, visual_feature, position_key ... dropped);
  `comment_datetime` from DD/MM/YYYY or YYYY-MM-DD + time only (ambiguous or date-only -> NULL);
  conflicts: different file for the same revision, or the same PDF under another supplier/PO.
- Qdrant: point id = `comments.id`; payload comment_id, document_id, project/document/revision,
  category, is_client_comment, status, text, resolution_text (closed only). Standards in Qdrant only,
  stable integer ids. `vectordb/comment_sync.py` syncs embeddings and updates payloads on resolve/reopen.
- RAG: no trace table; `trace` returned in the result and logged. Recommender history = closed comments
  with `resolution_text`; `suggest_resolution` writes only `ai_suggested_resolution` (+ "Referenced
  standards: ..." line) and `ai_confidence_percent` (None when faithfulness failed).
- `cems_cli.py`: JSON CLI for the Express routes. `rebuild-vectors --confirm` recreates both collections
  (old points had UUID ids) and re-embeds from Postgres.
- Demo, system report, live smoke and evaluation moved to the final schema (report gates count
  `documents` / `comments` / `embedded`; no trace rows are written any more).
- The extractor still writes position_key / reply columns to the CSV; ingest drops them (reported in
  `dropped_columns`).
- `database/migrations/` removed (both 001 files): the live database already is the final schema.
Verified here: 270 passed with real PostgreSQL 16 (256 passed + 14 skipped without it); demo, live smoke
(Postgres, temp database, Qdrant) and the report's infrastructure gate against a real Qdrant 1.12.4 server.
NOT verified: Ollama embeddings, the real LLM.
