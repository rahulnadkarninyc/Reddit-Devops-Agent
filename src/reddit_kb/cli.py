from __future__ import annotations

import argparse
import json
import os
import sys

from reddit_kb.embed_chroma import run_embed
from reddit_kb.eval_checklist import run_eval
from reddit_kb.ingest import run_ingest
from reddit_kb.logging_config import setup_logging
from reddit_kb.query_api import create_app, search_themes
from reddit_kb.settings import Settings
from reddit_kb.themes_llm import run_themes


def ingest_main() -> None:
    setup_logging()
    sys.exit(run_ingest(Settings()))


def themes_main() -> None:
    setup_logging()
    p = argparse.ArgumentParser(description="Extract themes from ingested posts")
    p.add_argument("--batch-size", type=int, default=25)
    args = p.parse_args()
    sys.exit(run_themes(Settings(), batch_size=args.batch_size))


def embed_main() -> None:
    setup_logging()
    sys.exit(run_embed(Settings()))


def eval_main() -> None:
    setup_logging()
    p = argparse.ArgumentParser(description="Print theme eval checklist")
    p.add_argument("--sample-n", type=int, default=5)
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()
    sys.exit(run_eval(Settings(), sample_n=args.sample_n, seed=args.seed))


def api_main() -> None:
    setup_logging()
    import uvicorn

    p = argparse.ArgumentParser(description="Run query API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    os.environ.setdefault("REDDIT_KB_ROOT", str(Settings().reddit_kb_root))
    settings = Settings().resolve_paths()
    app = create_app(settings)
    uvicorn.run(app, host=args.host, port=args.port)


def query_main() -> None:
    setup_logging()
    p = argparse.ArgumentParser(description="CLI semantic search over theme KB")
    p.add_argument("q", help="Natural language query")
    p.add_argument("-k", type=int, default=8, help="Number of themes")
    args = p.parse_args()
    settings = Settings().resolve_paths()
    try:
        res = search_themes(settings, args.q, k=args.k)
    except (RuntimeError, FileNotFoundError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    print(res.model_dump_json(indent=2))
