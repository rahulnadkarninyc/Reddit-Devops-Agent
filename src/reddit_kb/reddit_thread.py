from __future__ import annotations

import logging
from typing import Any

from reddit_kb.models import CommentSnippet

log = logging.getLogger(__name__)


def _walk_t1(
    children: list[Any],
    depth: int,
    max_depth: int,
    acc: list[dict[str, Any]],
) -> None:
    if not isinstance(children, list):
        return
    for ch in children:
        if not isinstance(ch, dict):
            continue
        kind = ch.get("kind")
        if kind == "more":
            continue
        if kind != "t1":
            continue
        d = ch.get("data") or {}
        if not isinstance(d, dict):
            continue
        body = str(d.get("body") or "").strip()
        if not body or body in ("[removed]", "[deleted]"):
            continue
        cid = d.get("id")
        if not cid:
            continue
        try:
            score = int(d.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        acc.append({"id": str(cid), "score": score, "body": body, "depth": depth})
        if depth >= max_depth:
            continue
        replies = d.get("replies")
        if isinstance(replies, dict):
            inner = replies.get("data") or {}
            inner_children = inner.get("children")
            if isinstance(inner_children, list):
                _walk_t1(inner_children, depth + 1, max_depth, acc)


def extract_top_comments_from_thread_json(
    root: Any,
    *,
    top_n: int,
    max_comment_chars: int,
    max_comment_depth: int,
) -> list[CommentSnippet]:
    """
    Parse Reddit thread response: a JSON array [post_listing, comments_listing] or wrapped.
    Skips kind 'more' (no expansion in v1).
    """
    listings: list[Any] = []
    if isinstance(root, list):
        listings = root
    elif isinstance(root, dict) and root.get("kind") == "Listing":
        listings = [root]
    else:
        log.debug("Unexpected thread JSON root type: %s", type(root).__name__)
        return []

    flat: list[dict[str, Any]] = []
    for listing in listings:
        if not isinstance(listing, dict):
            continue
        data = listing.get("data") or {}
        children = data.get("children") if isinstance(data, dict) else None
        if not isinstance(children, list):
            continue
        _walk_t1(children, depth=0, max_depth=max_comment_depth, acc=flat)

    flat.sort(key=lambda x: x["score"], reverse=True)
    out: list[CommentSnippet] = []
    for item in flat[:top_n]:
        body = item["body"]
        if len(body) > max_comment_chars:
            body = body[:max_comment_chars] + "…[truncated]"
        out.append(
            CommentSnippet(
                id=item["id"],
                score=int(item["score"]),
                body=body,
                depth=int(item["depth"]),
            )
        )
    return out
