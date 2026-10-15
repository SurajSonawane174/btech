# CEMS AI Automation Layer

Multi-DB + RBAC + Semantic Search + Agentic RAG Compliance Checking +
AI Resolution Recommender — built on top of `comment_extractor.py`'s
real output schema and reusing its `Config`/`LLMClient` contract.

## What's in here

| Module | What it does | Addresses |
|---|---|---|
| `database/schema.sql` + `db.py` | Postgres schema matching `comment_extractor.py`'s real `COLUMNS` output field-for-field, plus role-scoped RBAC, a lightweight entity graph, and a RAG trace-log table | Multi-DB, RBAC |
| `vectordb/qdrant_client.py` + `embedder.py` | Two Qdrant collections (comments, standards_chunks), local Ollama embeddings — no API cost | Multi-DB, Semantic Search |
| `ingest.py` | Bridges `comment_extractor.py`'s real output into both DBs | Multi-DB |
| `standards_corpus/seed_standards.py` | **[PLACEHOLDER]** 3 illustrative standard excerpts (AWS D1.1, ASME B31.3, IS 800) — swap for PRAJ's real referenced standards before production use | Agentic RAG |
| `agentic_rag/compliance_check.py` | Query decomposition → multi-hop retrieval → synthesis → **faithfulness self-check** (verified to actually catch unsupported claims, not just report them) → full trace log | AI Automation (novelty) |
| `recommender/resolution_recommender.py` | Combines similar-past-comments + faithfulness-verified standards grounding into a drafted resolution, confidence-scored by source availability (40/65/90%, never near-certain) | AI Automation (novelty) |

## What's verified vs. what needs a live run

**Verified this session**, with mocked DB/LLM + real in-memory Qdrant:
- UID parsing against the real `make_uid()` format
- Full ingestion logic (project/drawing/revision grouping, embedding, Qdrant upsert)
- Both Qdrant collections, real retrieval behavior
- **Agentic RAG full 3-call loop** (decompose → synthesize → faithfulness check) in correct order
- **Edge case: no checkable requirement** → correctly short-circuits, no wasted LLM calls
- **Edge case: hallucinated citation** → correctly caught and flagged by the faithfulness check, not silently trusted
- **Resolution recommender, all 3 confidence tiers** (both sources / similar-only / neither) — correct drafts and scores in each

**Not yet verified**: a live run against real Docker containers (Postgres/Qdrant/Ollama) and a real OpenRouter LLM call — no Docker or API key in this sandbox. Everything above was tested with the exact same call shapes a real `LLMClient`/live DB would receive, so logic bugs should be caught; what's untested is purely the live-environment wiring.

## Setup

```bash
cp .env.example .env
docker compose up -d
docker compose ps
docker exec -it cems_ollama ollama pull nomic-embed-text
pip install -r requirements.txt
```

## Run, in order

```bash
# 1. Ingest comment_extractor.py's output into Postgres + Qdrant
python ingest.py --input output/master_comments.csv

# 2. Seed the (placeholder) standards corpus
python standards_corpus/seed_standards.py

# 3. Try the agentic compliance check on a real comment
python3 -c "
import sys; sys.path.insert(0, '.')
from comment_extractor import Config, LLMClient   # reuse the real pipeline's client
from agentic_rag.compliance_check import check_compliance

cfg = Config.from_yaml('config.yaml')
llm = LLMClient(cfg)
result = check_compliance('Weld symbol not per AWS D1.1, please revise', llm)
print(result['answer'])
print('faithfulness_passed:', result['faithfulness_passed'])
"

# 4. Try a full resolution recommendation
python3 -c "
import sys; sys.path.insert(0, '.')
from comment_extractor import Config, LLMClient
from recommender.resolution_recommender import recommend_resolution

cfg = Config.from_yaml('config.yaml')
llm = LLMClient(cfg)
result = recommend_resolution('Pipe support spacing exceeds allowable span', llm)
print(result['draft_resolution'])
print('confidence:', result['confidence_percent'], '%  basis:', result['basis'])
"
```

## Verify the databases directly

```bash
docker exec -it cems_postgres psql -U cems -d cems -c "
  SELECT comment_uid, comment_category, classification_method, comment_source
  FROM comments LIMIT 10;
"
curl -s http://localhost:6333/collections/comments | python3 -m json.tool | grep points_count
curl -s http://localhost:6333/collections/standards_chunks | python3 -m json.tool | grep points_count
```

## RBAC — what's actually enforced

`db.PERMISSIONS` is the real permission matrix. `db.can(user_id, project_id, action)`
is the enforcement point your API layer calls before any mutating action.
Roles are **per-project** (`project_memberships`), not global.

## Why "faithfulness self-check" matters for the demo

This is the single thing that separates this from a naive RAG wrapper, and
it's worth showing Vahida directly: feed it a comment, show the retrieved
excerpt, show the LLM's synthesized answer, then show the faithfulness
check's verdict. In the hallucination test above, the synthesis step
**fabricated a citation to a standard that was never retrieved** — and the
faithfulness check caught it and returned `passed: False`. That's the
concrete, demoable evidence that the system checks itself rather than
blindly trusting its own output.

## Before using this beyond a demo

- Swap `standards_corpus/seed_standards.py`'s placeholder excerpts for
  PRAJ's actual referenced standards
- Get real OpenRouter credit / confirm rate limits for the LLM calls
  (3 calls per compliance check, 4 per resolution recommendation —
  budget accordingly, this adds up fast at scale)
- Run the full stack live and re-verify against real Docker containers

## Coordination note

If your teammate is independently building multi-DB, sync `schema.sql`
with them before either of you goes further — that's the one genuine
merge-conflict risk. Everything else here is additive.
