from __future__ import annotations

import json
import logging
from pathlib import Path

from reddit_kb.models import PostRecord

log = logging.getLogger(__name__)


def load_posts_jsonl(path: Path) -> dict[str, PostRecord]:
    if not path.exists():
        return {}
    by_id: dict[str, PostRecord] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rec = PostRecord.model_validate(obj)
                by_id[rec.id] = rec
            except (json.JSONDecodeError, ValueError) as e:
                log.warning("Skip bad JSONL line: %s", e)
    return by_id


def write_posts_jsonl(path: Path, posts: dict[str, PostRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    sorted_posts = sorted(posts.values(), key=lambda p: (p.subreddit, p.created_utc))
    with tmp.open("w", encoding="utf-8") as f:
        for p in sorted_posts:
            f.write(p.model_dump_json() + "\n")
    tmp.replace(path)
    log.info("Wrote %s posts to %s", len(posts), path)
