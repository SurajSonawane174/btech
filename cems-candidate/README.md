# CEMS AI engine (Python side)

Extraction, loading, semantic search, standards RAG and AI draft resolutions for CEMS, written
against the FINAL database schema (`database/schema.sql`: `documents`, `users`, `comments`).
The web API, login and roles live in the Express backend; it calls this engine through
`cems_cli.py`.

| Module | What it does |
|---|---|
| `comment_extractor.py` | PDF -> comment rows (`output/master_comments.csv`) |
| `ingest.py` | CSV -> `documents` + `comments` (allowlist mapping, idempotent), then embedding sync |
| `database/db.py` | Postgres access for the 3-table schema (bigint ids) |
| `vectordb/qdrant_client.py` | Qdrant collections `comments` (point id = `comments.id`) and `standards_chunks` (integer ids) |
| `vectordb/comment_sync.py` | Embedding sync, similar search, resolve / reopen with Qdrant payload updates |
| `standards_corpus/seed_standards.py` | **Placeholder** standards (AWS D1.1, ASME B31.3, IS 800) -> Qdrant only |
| `agentic_rag/compliance_check.py` | Decompose -> multi-hop retrieve -> synthesise -> citation check -> faithfulness check; returns the trace |
| `recommender/resolution_recommender.py` | Draft resolution from resolved similar comments + verified standards; stores only the AI columns |
| `cems_cli.py` | JSON command line for the Express backend |

## Data rules

- A document revision is one `documents` row, unique on `unique_doc_revision`
  (project, document number, revision, supplier, supplier PO). A missing revision is stored as `NA`.
- Project number, supplier name and supplier PO come from the upload form (`--project --supplier --po`);
  they are never defaulted.
- `comments.comment_id` is globally unique; ingest uses `ON CONFLICT (comment_id) DO NOTHING`.
  The same PDF uploaded under a second supplier/PO is reported as a conflict and not stored.
- Status values: `open`, `closed`. Resolve sets `closed` + `resolution_text` + `resolved_at`;
  reopen sets `open` and clears `resolved_at`.
- AI drafts go to `ai_suggested_resolution` / `ai_confidence_percent` only, ending with a
  "Referenced standards: ..." line. Only a human approval writes `resolution_text`.
- Standards text, vectors and RAG traces are never stored in Postgres.

## Setup

```
cp .env.example .env
docker compose up -d                 # postgres + qdrant
ollama pull nomic-embed-text         # native Ollama on the host
pip install -r requirements.txt
```

One-off after moving to the final schema (old Qdrant points used UUID ids):

```
python cems_cli.py rebuild-vectors --confirm     # recreates both collections, re-embeds, re-seeds
```

## Commands (all print one JSON object)

```
python cems_cli.py ingest --input output/master_comments.csv --project P-1001 --supplier "ACME" --po PO-4512
python cems_cli.py embed-sync
python cems_cli.py search --text "check weld size" --project P-1001 --only-resolved
python cems_cli.py search --comment-id 12
python cems_cli.py suggest --comment-id 12
python cems_cli.py resolve --comment-id 12 --text-stdin      # approved text on stdin
python cems_cli.py reopen --comment-id 12
python cems_cli.py seed-standards
python -m pytest -q tests
```

Real-PostgreSQL tests run when `CEMS_TEST_DATABASE_URL` points at a server where the user may
create databases; each test uses its own throw-away database.

## Before using this beyond a demo

- Replace the placeholder standards with PRAJ's referenced standards.
- Verify real embeddings (Ollama) and the real LLM; the automated tests use stand-ins for both.
