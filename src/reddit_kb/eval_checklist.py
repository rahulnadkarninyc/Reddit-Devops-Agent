from __future__ import annotations

import json
import logging
import random

from reddit_kb.raw_store import load_posts_jsonl
from reddit_kb.settings import Settings

log = logging.getLogger(__name__)


def run_eval(settings: Settings, sample_n: int = 5, seed: int | None = None) -> int:
    settings = settings.resolve_paths()
    themes_path = settings.reddit_kb_root / "data" / "themes" / "themes.json"
    if not themes_path.exists():
        log.error("Missing %s; run reddit-kb-themes first", themes_path)
        return 1

    with themes_path.open(encoding="utf-8") as f:
        bundle = json.load(f)
    themes = bundle.get("themes") or []
    if not isinstance(themes, list) or not themes:
        log.error("No themes in bundle")
        return 1

    if seed is not None:
        random.seed(seed)
    picks = random.sample(themes, min(sample_n, len(themes)))

    posts_by_id = load_posts_jsonl(settings.raw_posts_path)

    lines = [
        "=== Theme quality spot-check (human review) ===",
        f"taxonomy_version: {bundle.get('taxonomy_version')}",
        f"prompt_hash: {bundle.get('prompt_hash')}",
        f"total_themes: {len(themes)}",
        "",
        "For each theme: verify source posts support the label; note merges to do.",
        "",
    ]
    for i, t in enumerate(picks, 1):
        if not isinstance(t, dict):
            continue
        label = t.get("theme_label", "")
        desc = t.get("description", "")
        pids = t.get("source_post_ids") or []
        lines.append(f"--- Sample {i}: {label} ---")
        lines.append(f"description: {desc}")
        lines.append(f"source_post_ids ({len(pids)}): {pids[:12]}{'…' if len(pids) > 12 else ''}")
        for pid in pids[:3]:
            p = posts_by_id.get(str(pid))
            if p:
                lines.append(f"  post {pid} r/{p.subreddit}: {p.title[:120]}")
            else:
                lines.append(f"  post {pid}: (not in local posts.jsonl)")
        lines.append("")

    mapped = 0
    for t in themes:
        if not isinstance(t, dict):
            continue
        pids = t.get("source_post_ids") or []
        if isinstance(pids, list) and pids:
            mapped += 1
    coverage = mapped / len(themes) if themes else 0.0
    lines.append(f"Approx. themes with ≥1 source post id: {mapped}/{len(themes)} ({coverage:.0%})")

    covered_posts: set[str] = set()
    for t in themes:
        if not isinstance(t, dict):
            continue
        for pid in t.get("source_post_ids") or []:
            covered_posts.add(str(pid).removeprefix("t3_"))
    ingested = len(posts_by_id)
    overlap = len(covered_posts & set(posts_by_id.keys()))
    post_cov = (overlap / ingested) if ingested else 0.0
    lines.append(
        f"Posts referenced by ≥1 theme (in local store): {overlap}/{ingested} ({post_cov:.0%})",
    )

    report = "\n".join(lines)
    print(report)
    out_path = settings.reddit_kb_root / "data" / "themes" / "eval_sample.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report + "\n", encoding="utf-8")
    log.info("Wrote %s", out_path)
    return 0
