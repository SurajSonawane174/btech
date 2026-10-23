# CEMS evaluation harness

Scores extractor output (`output/master_comments.csv`) against ground truth labelled by a person.
There is no labelled real dataset yet, so **no real-world accuracy figure exists**. The harness
says so in every report until a dataset of kind `real` has been scored.

## Files

| File | Purpose |
|---|---|
| `metrics.py` | Metric functions (pure, unit-tested in `tests/test_evaluation.py`) |
| `run_evaluation.py` | Command line: gold + predictions -> `evaluation_report.json` |
| `synthetic_eval.py` | Builds synthetic PDFs with known ground truth, runs the real extractor, scores it as kind `synthetic` |
| `templates/gold_comments_template.csv` | Empty gold file for comments (header only) |
| `templates/gold_retrieval_template.csv` | Empty gold file for retrieval (header only) |

## Ground-truth format: comments (`gold_comments.csv`)

One row per real review comment visible on the drawing (what a reviewer would count as one
comment). Replies in a PDF thread are **not** separate rows. They belong to their root comment.

| Column | Required | Meaning |
|---|---|---|
| `source_file` | yes | PDF file name exactly as given to the extractor, e.g. `PRJ_PID_DWG101_RA.pdf` |
| `page` | yes | 1-based page number |
| `comment_text` | yes | The comment text as written (spelling as on the drawing) |
| `category` | no | Correct category label, e.g. `technical` / `aesthetic`. Empty = not labelled |
| `duplicate_group` | no | Any label shared by comments that repeat the same request **in the same file**. Empty = unique. If the column is absent, duplicate metrics are reported as `no_labels` |

Example rows:

```
source_file,page,comment_text,category,duplicate_group
PRJ_PID_DWG101_RA.pdf,1,Verify fillet weld size per AWS D1.1,technical,
PRJ_PID_DWG101_RA.pdf,1,Title block font too small,aesthetic,f1
PRJ_PID_DWG101_RA.pdf,2,Title block font too small,aesthetic,f1
```

## Ground-truth format: retrieval (`gold_retrieval.csv`)

One row per (query, relevant comment) pair. A query with several relevant comments has
several rows. A query row with an empty `relevant_comment_text` is listed but is not scored.

| Column | Meaning |
|---|---|
| `query_text` | A new comment used as the search query |
| `relevant_comment_text` | Text of a stored comment that a reviewer judges relevant (exact stored text) |

Retrieval results are either a JSON file `{"query text": ["retrieved comment text", ...]}` (best
first), or `--live-retrieval`, which runs the real Ollama embedding and Qdrant search.

## Metrics

| Task | Metric | How |
|---|---|---|
| Extraction | precision, recall, F1 | One-to-one match on same `source_file` + `page` and RapidFuzz ratio >= 90 on normalised text (`--match-threshold`) |
| Classification | accuracy, macro-F1, per-class P/R/F1 | Only over **matched** comments with a gold label (a missed comment is an extraction error, not a class error) |
| Duplicates | pair precision, recall, F1 | Pairs within each gold `duplicate_group` vs pairs implied by `duplicate_of` (connected components), both restricted to matched comments |
| Retrieval | precision@k, recall@k, hit rate@k | Mean over queries that have at least one relevant label; precision@k divides by k |

Undefined values (zero denominator) are `null`, never 0 or 1. Each task has a `status`: `ok`,
`no_labels` (gold has no labels for it) or `no_data` (nothing on either side). Raw counts
(`tp`, `fp`, `fn`, `n`) are always included.

## Running

```
python evaluation/synthetic_eval.py                       # synthetic sanity check (kind: synthetic)
python evaluation/run_evaluation.py --name pilot-10 --kind real --gold labels/gold_comments.csv --pred output/master_comments.csv
python generate_system_report.py --evaluation evaluation_report.json
```

Use `--kind real` only for gold files labelled by a person from real drawings. Anything generated
by code is `synthetic`. Do not label gold data by copying extractor output: that measures
agreement with itself.

## Suggested first real dataset

5-10 PRAJ PDFs covering native annotations, a rotated sheet, a reply thread and, if available,
one flattened page. Label every comment, its category and duplicates. Keep the PDFs and labels
outside git if they are confidential.
