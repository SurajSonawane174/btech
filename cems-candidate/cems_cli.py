"""
cems_cli.py -- one entry point the Express backend can call for every Python-side operation.

Each command prints ONE JSON object to stdout (logs go to stderr) and exits 0 on success,
1 on a handled error ({"ok": false, "error": "..."}), 2 on bad arguments.

  ingest           --input CSV --project P --supplier S --po PO [--allow-unresolved] [--no-embed]
  embed-sync       [--ids 12,13]                  embed comments with embedded=false (or exactly these ids)
  search           (--text "..." | --comment-id 12) [--top-k 5] [--project P] [--category technical]
                   [--only-resolved] [--min-score 0.55]
  suggest          --comment-id 12 [--config config.yaml]   AI draft -> ai_suggested_resolution/ai_confidence_percent
  resolve          --comment-id 12 (--text "..." | --text-stdin)   human approval: status 'closed'
  reopen           --comment-id 12                status 'open', resolved_at NULL
  seed-standards   [--recreate]                   placeholder standards -> Qdrant only
  rebuild-vectors  --confirm                      DESTRUCTIVE: recreate both collections, re-embed, re-seed

Example from Node:
  execFile("python", ["cems_cli.py", "resolve", "--comment-id", String(id), "--text-stdin"], ...)
  and write the approved text to the child's stdin.
"""
import argparse
import json
import logging
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s | %(levelname)s | %(message)s")


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def emit(obj, code=0):
    print(json.dumps(obj, default=_json_default, ensure_ascii=False))
    return code


def _llm(config_path):
    import comment_extractor as ce            # loads .env next to the extractor
    return ce.LLMClient(ce.Config.from_yaml(Path(config_path)))


def run(args) -> dict:
    from database import db
    from vectordb import comment_sync
    db.init_pool()
    if args.cmd == "ingest":
        import ingest
        return ingest.ingest_dataframe(ingest.read_extractor_csv(args.input), args.input, args.project,
                                       args.supplier, args.po, allow_unresolved=args.allow_unresolved,
                                       embed=not args.no_embed)
    if args.cmd == "embed-sync":
        ids = [int(x) for x in args.ids.split(",") if x.strip()] if args.ids else None
        return comment_sync.sync_embeddings(ids=ids)
    if args.cmd == "search":
        return comment_sync.find_similar(text=args.text, comment_pk=args.comment_id, top_k=args.top_k,
                                         score_threshold=args.min_score, praj_project_number=args.project,
                                         comment_category=args.category, only_resolved=args.only_resolved)
    if args.cmd == "suggest":
        from recommender.resolution_recommender import suggest_resolution
        return suggest_resolution(args.comment_id, _llm(args.config))
    if args.cmd == "resolve":
        text = sys.stdin.read() if args.text_stdin else args.text
        return comment_sync.resolve_comment(args.comment_id, text)
    if args.cmd == "reopen":
        return comment_sync.reopen_comment(args.comment_id)
    if args.cmd == "seed-standards":
        from standards_corpus import seed_standards
        return seed_standards.seed(recreate=args.recreate)
    if args.cmd == "rebuild-vectors":
        from standards_corpus import seed_standards
        comments = comment_sync.rebuild_comment_vectors()
        standards = seed_standards.seed(recreate=True)
        return {"comments": comments, "standards": standards}
    raise ValueError(f"unknown command {args.cmd}")


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--input", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--supplier", required=True)
    p.add_argument("--po", required=True)
    p.add_argument("--allow-unresolved", action="store_true")
    p.add_argument("--no-embed", action="store_true")
    p = sub.add_parser("embed-sync")
    p.add_argument("--ids", default=None, help="comma-separated comments.id values")
    p = sub.add_parser("search")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--comment-id", type=int)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--project", default=None)
    p.add_argument("--category", default=None)
    p.add_argument("--only-resolved", action="store_true")
    p.add_argument("--min-score", type=float, default=0.55)
    p = sub.add_parser("suggest")
    p.add_argument("--comment-id", type=int, required=True)
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p = sub.add_parser("resolve")
    p.add_argument("--comment-id", type=int, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--text-stdin", action="store_true")
    p = sub.add_parser("reopen")
    p.add_argument("--comment-id", type=int, required=True)
    p = sub.add_parser("seed-standards")
    p.add_argument("--recreate", action="store_true")
    p = sub.add_parser("rebuild-vectors")
    p.add_argument("--confirm", action="store_true", help="required: this deletes and rebuilds both collections")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "rebuild-vectors" and not args.confirm:
        return emit({"ok": False, "error": "rebuild-vectors deletes both Qdrant collections; add --confirm"}, 2)
    try:
        return emit({"ok": True, "command": args.cmd, "result": run(args)})
    except (LookupError, ValueError) as e:
        return emit({"ok": False, "command": args.cmd, "error": str(e)}, 1)
    except Exception as e:
        logging.getLogger("cems_cli").exception("command failed")
        return emit({"ok": False, "command": args.cmd, "error": f"{type(e).__name__}: {e}"}, 1)


if __name__ == "__main__":
    sys.exit(main())
