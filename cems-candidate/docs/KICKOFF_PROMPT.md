# First message to paste into Claude Code

Run `claude` from the repo root (CLAUDE.md is loaded automatically). Do not run `/init`; CLAUDE.md is already written.

---
Read CLAUDE.md, docs/HANDOFF.md and docs/ROADMAP.md. Do not write code yet.
1. Summarize the project, current state and hard rules in 10 bullets.
2. List the 5 biggest risks you see in the current code or plan.
3. Propose a Phase 0 plan of at most 10 steps and wait for my approval.
Rules for this project: small commits, mock-based tests for logic changes, live check via `python generate_system_report.py` for behaviour changes, no accuracy claims without ground truth, no secrets in commits, ask before large refactors of comment_extractor.py.
---

## Follow-up prompts, in order
1. "Execute Phase 0. Stop after each numbered step so I can review the diff."
2. "Phase 1: fix the metadata/UID collision first. Write a failing test that reproduces 250 rows collapsing to 50, then fix it."
3. "Build the Rev A / Rev B fixture and the revision diff."
4. "Phase 2: port eval_metrics.py and ablation_study.py to the current schema. Add the retrieval hit@k test on synthetic paraphrases."
5. "Phase 3 item 1, then 2, then 3. Each needs a metric."

## Files to copy from the old machine into the repo
`comment_extractor.py`, `config.yaml`, `requirements.txt`, `database/`, `vectordb/`, `agentic_rag/`, `recommender/`, `standards_corpus/`, `ingest.py`, `generate_system_report.py`, `docker-compose.yml`, `input/` (test PDFs).
Copy YOUR local versions: they contain fixes made after my last zip. Do not copy `.venv`, `output/`, or `.env` (create it from `.env.example` and add your own key).
From the old `btech` folder, put these in `legacy/`: `showcase_ready/` (eval_metrics.py, ablation_study.py, rls_policies.sql, local_vlm_classifier.py, glm_ocr_titleblock.py, PAPER_ADDITIONS.md), `doc_process.py`, and the IEEE paper PDF and PPT.
