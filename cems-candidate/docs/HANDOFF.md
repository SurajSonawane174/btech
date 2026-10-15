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
        -> ingest.py -> Postgres (structured, RBAC, resolutions, traces)
                     -> Ollama embed -> Qdrant: comments
standards (placeholder) -> embed -> Qdrant: standards_chunks
comment -> compliance_check (decompose -> multi-hop -> synthesize -> faithfulness) -> trace
comment -> recommender (similar comments + resolutions + verified standards) -> draft -> human approval
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
3. Knowledge graph tables exist (`entities`, `comment_entity_edges`) but nothing writes to them.
4. No API, UI, approval workflow, or audit trail beyond `rag_query_traces`.
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
