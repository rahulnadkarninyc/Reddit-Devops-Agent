from __future__ import annotations

import logging
import time
from pathlib import Path

from reddit_kb.config_loader import ingest_options, subreddit_names
from reddit_kb.models import PostRecord
from reddit_kb.raw_store import load_posts_jsonl, write_posts_jsonl
from reddit_kb.reddit_client import RedditClient
from reddit_kb.reddit_public import RedditPublicJsonClient
from reddit_kb.settings import Settings

log = logging.getLogger(__name__)


def run_ingest(settings: Settings) -> int:
    settings = settings.resolve_paths()
    root = Path(settings.reddit_kb_root)

    opts = ingest_options(root)
    posts_per = int(opts.get("posts_per_subreddit", 500))
    time_filter = str(opts.get("time_filter", "month"))
    max_body = int(opts.get("max_selftext_chars", 8000))
    public_delay = float(opts.get("public_request_delay_sec", 1.5))
    subreddit_delay = float(opts.get("subreddit_delay_sec", 0))
    include_comments = bool(opts.get("include_comments", False))
    posts_with_comments = int(opts.get("posts_with_comments_per_subreddit", 100))
    top_comments_per_post = int(opts.get("top_comments_per_post", 20))
    max_comment_chars = int(opts.get("max_comment_chars", 500))
    max_comment_depth = int(opts.get("max_comment_depth", 6))
    comment_fetch_delay = float(opts.get("comment_fetch_delay_sec", 1.5))
    thread_json_limit = int(opts.get("thread_json_limit", 200))

    use_public = settings.reddit_use_public_json or not (
        settings.reddit_client_id and settings.reddit_client_secret
    )
    if use_public:
        log.info(
            "Using public Reddit JSON (no OAuth). Set REDDIT_USE_PUBLIC_JSON=0 and "
            "REDDIT_CLIENT_* to use the official API instead.",
        )
    else:
        log.info("Using Reddit OAuth API")

    subs = subreddit_names(root)
    log.info(
        "Ingesting top %s per sub (%s subs), t=%s; comments=%s (cap %s/sub)",
        posts_per,
        len(subs),
        time_filter,
        include_comments,
        posts_with_comments if include_comments else 0,
    )

    existing = load_posts_jsonl(settings.raw_posts_path)
    log.info("Loaded %s existing posts from disk", len(existing))

    if use_public:
        client_ctx = RedditPublicJsonClient(
            settings.reddit_user_agent,
            page_delay_sec=public_delay,
        )
    else:
        client_ctx = RedditClient(
            settings.reddit_client_id,
            settings.reddit_client_secret,
            settings.reddit_user_agent,
        )

    with client_ctx as client:
        for i, sub in enumerate(subs):
            if i > 0 and subreddit_delay > 0:
                time.sleep(subreddit_delay)
            try:
                children = client.iter_subreddit_top(sub, time_filter, posts_per)
            except Exception as e:
                log.exception("Failed subreddit r/%s: %s", sub, e)
                continue
            for idx, ch in enumerate(children):
                rec = PostRecord.from_reddit_child(ch, time_filter)
                if rec is None:
                    continue
                if len(rec.selftext) > max_body:
                    rec = rec.model_copy(
                        update={"selftext": rec.selftext[:max_body] + "\n…[truncated]"}
                    )
                prev = existing.get(rec.id)
                if include_comments and idx < posts_with_comments:
                    try:
                        snippets = client.fetch_post_thread_top_comments(
                            sub,
                            rec.id,
                            sort="top",
                            thread_limit=thread_json_limit,
                            top_comments_per_post=top_comments_per_post,
                            max_comment_chars=max_comment_chars,
                            max_comment_depth=max_comment_depth,
                        )
                        rec = rec.model_copy(update={"top_comments": snippets, "schema_version": 2})
                    except Exception as e:
                        log.warning("Thread fetch failed r/%s post %s: %s", sub, rec.id, e)
                        if prev and prev.top_comments:
                            rec = rec.model_copy(
                                update={"top_comments": prev.top_comments, "schema_version": 2},
                            )
                    time.sleep(comment_fetch_delay)
                else:
                    if prev and prev.top_comments:
                        rec = rec.model_copy(
                            update={"top_comments": prev.top_comments, "schema_version": 2},
                        )
                existing[rec.id] = rec
            log.info("r/%s: merged %s total posts in index", sub, len(existing))

    write_posts_jsonl(settings.raw_posts_path, existing)
    return 0
