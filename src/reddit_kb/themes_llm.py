from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

from reddit_kb.models import PostRecord, ThemeRecord
from reddit_kb.raw_store import load_posts_jsonl
from reddit_kb.settings import Settings

log = logging.getLogger(__name__)

BATCH_SYSTEM = """You analyze Reddit posts from DevOps, Kubernetes, cloud, and SRE communities.
Extract recurring pain points and questions as concise themes. Each item may include top comments from that thread—use them to infer what the community cares about, in addition to the post title/body.
Rules:
- Each theme must only cite post ids that appear in the provided batch (the "id" field). Do not use comment ids in source_post_ids.
- Use short theme_label (3-8 words).
- description: 1-3 sentences on what the community struggles with or asks about.
- pain_point_type: one of tooling, career, architecture, incident, cost, security, learning_curve, process, vendor, other.
- example_question_phrases: up to 4 short phrases typical of this theme.
- confidence: 0.0-1.0
Return strict JSON: {"themes":[...]} with no other keys."""

MERGE_SYSTEM = """You merge duplicate or overlapping DevOps/SRE community themes.
Input is a JSON object {"themes": [...]} with theme objects that may overlap.
Output strict JSON: {"themes": [...]} where each output theme merges overlaps:
- theme_label: canonical short name
- description: unified description
- pain_point_type: single best category
- example_question_phrases: union, max 6 distinct phrases
- confidence: max of merged inputs, capped at 1.0
- source_post_ids: union of all source_post_ids from merged themes (dedupe)
Return only JSON."""


def _prompt_hash() -> str:
    h = hashlib.sha256((BATCH_SYSTEM + MERGE_SYSTEM).encode()).hexdigest()
    return h[:16]


def _taxonomy_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:48] or "theme"


def _chat_json(client: OpenAI, model: str, system: str, user: str) -> dict[str, Any]:
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = r.choices[0].message.content or "{}"
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object from model")
    usage = r.usage
    if usage:
        log.info(
            "LLM tokens prompt=%s completion=%s",
            usage.prompt_tokens,
            usage.completion_tokens,
        )
    return data


def _posts_for_batch(posts: list[PostRecord]) -> str:
    lines = []
    for p in posts:
        comments_out: list[dict[str, Any]] = []
        for c in p.top_comments[:25]:
            comments_out.append(
                {
                    "score": c.score,
                    "depth": c.depth,
                    "body": c.body[:2000],
                }
            )
        lines.append(
            json.dumps(
                {
                    "id": p.id,
                    "subreddit": p.subreddit,
                    "title": p.title,
                    "selftext": p.selftext[:4000],
                    "score": p.score,
                    "num_comments": p.num_comments,
                    "comments": comments_out,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _parse_theme_objects(raw_themes: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in raw_themes:
        if not isinstance(t, dict):
            continue
        out.append(t)
    return out


def extract_batch_themes(
    client: OpenAI,
    model: str,
    posts: list[PostRecord],
) -> list[dict[str, Any]]:
    user = "Posts JSON lines (one post per line):\n" + _posts_for_batch(posts)
    data = _chat_json(client, model, BATCH_SYSTEM, user)
    themes = data.get("themes")
    if not isinstance(themes, list):
        return []
    return _parse_theme_objects(themes)


def merge_theme_dicts(
    client: OpenAI,
    model: str,
    theme_dicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    user = json.dumps({"themes": theme_dicts}, ensure_ascii=False)
    if len(user) > 100_000:
        user = user[:100_000] + "\n…[truncated for merge]"
    data = _chat_json(client, model, MERGE_SYSTEM, user)
    themes = data.get("themes")
    if not isinstance(themes, list):
        return []
    return _parse_theme_objects(themes)


def hierarchical_merge(
    client: OpenAI,
    model: str,
    theme_dicts: list[dict[str, Any]],
    chunk_size: int = 45,
) -> list[dict[str, Any]]:
    if not theme_dicts:
        return []
    if len(theme_dicts) <= chunk_size:
        return merge_theme_dicts(client, model, theme_dicts)
    merged_level: list[dict[str, Any]] = []
    for i in range(0, len(theme_dicts), chunk_size):
        chunk = theme_dicts[i : i + chunk_size]
        merged_level.extend(merge_theme_dicts(client, model, chunk))
    return hierarchical_merge(client, model, merged_level, chunk_size=chunk_size)


def dicts_to_records(
    theme_dicts: list[dict[str, Any]],
    posts_by_id: dict[str, PostRecord],
    taxonomy_version: str,
    prompt_hash: str,
) -> list[ThemeRecord]:
    records: list[ThemeRecord] = []
    for t in theme_dicts:
        label = str(t.get("theme_label") or "Untitled theme").strip()
        desc = str(t.get("description") or "").strip()
        ppt = str(t.get("pain_point_type") or "other").strip()
        phrases = t.get("example_question_phrases")
        if not isinstance(phrases, list):
            phrases = []
        phrases = [str(x) for x in phrases if isinstance(x, (str, int, float))][:8]
        try:
            conf = float(t.get("confidence", 0.7))
        except (TypeError, ValueError):
            conf = 0.7
        conf = max(0.0, min(1.0, conf))
        raw_ids = t.get("source_post_ids")
        if not isinstance(raw_ids, list):
            raw_ids = []
        pids: list[str] = []
        for x in raw_ids:
            s = str(x).removeprefix("t3_").strip()
            if s and s not in pids:
                pids.append(s)
        subs: list[str] = []
        for pid in pids:
            pr = posts_by_id.get(pid)
            if pr and pr.subreddit and pr.subreddit not in subs:
                subs.append(pr.subreddit)
        tid = f"{_slug(label)}-{uuid.uuid4().hex[:8]}"
        records.append(
            ThemeRecord(
                theme_id=tid,
                theme_label=label,
                description=desc,
                pain_point_type=ppt,
                example_question_phrases=phrases,
                confidence=conf,
                source_post_ids=pids,
                subreddits=subs,
                taxonomy_version=taxonomy_version,
                prompt_hash=prompt_hash,
            )
        )
    return records


def run_themes(settings: Settings, batch_size: int = 25) -> int:
    settings = settings.resolve_paths()
    if not settings.openai_api_key:
        log.error("Set OPENAI_API_KEY")
        return 1

    posts_by_id = load_posts_jsonl(settings.raw_posts_path)
    if not posts_by_id:
        log.error("No posts at %s; run reddit-kb-ingest first", settings.raw_posts_path)
        return 1

    posts_list = list(posts_by_id.values())
    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.openai_model
    taxonomy_version = _taxonomy_version()
    phash = _prompt_hash()

    all_partial: list[dict[str, Any]] = []
    for i in range(0, len(posts_list), batch_size):
        batch = posts_list[i : i + batch_size]
        try:
            partial = extract_batch_themes(client, model, batch)
        except Exception as e:
            log.exception("Batch %s failed: %s", i // batch_size, e)
            continue
        all_partial.extend(partial)
        log.info("Batch %s: +%s themes (total partial %s)", i // batch_size, len(partial), len(all_partial))

    if not all_partial:
        log.error("No themes extracted")
        return 1

    log.info("Merging %s partial themes…", len(all_partial))
    try:
        merged_dicts = hierarchical_merge(client, model, all_partial)
    except Exception as e:
        log.exception("Merge failed: %s", e)
        return 1

    records = dicts_to_records(merged_dicts, posts_by_id, taxonomy_version, phash)
    themes_path = settings.reddit_kb_root / "data" / "themes" / "themes.json"
    themes_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump() for r in records]
    with themes_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "taxonomy_version": taxonomy_version,
                "prompt_hash": phash,
                "theme_count": len(records),
                "themes": payload,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    log.info("Wrote %s themes to %s", len(records), themes_path)
    return 0
