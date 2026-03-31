from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class CommentSnippet(BaseModel):
    id: str
    score: int
    body: str
    depth: int = 0


class PostRecord(BaseModel):
    schema_version: int = 2
    id: str
    fullname: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str
    url: str
    ingested_at: str
    listing_time_filter: str
    top_comments: list[CommentSnippet] = Field(default_factory=list)

    @classmethod
    def from_reddit_child(
        cls,
        child_data: dict[str, Any],
        listing_time_filter: str,
    ) -> PostRecord | None:
        if child_data.get("kind") != "t3":
            return None
        d = child_data.get("data") or {}
        pid = d.get("id")
        if not pid:
            return None
        fullname = d.get("name") or f"t3_{pid}"
        ingested = datetime.now(timezone.utc).isoformat()
        return cls(
            schema_version=2,
            id=str(pid),
            fullname=str(fullname),
            subreddit=str(d.get("subreddit", "")).lower(),
            title=str(d.get("title") or ""),
            selftext=str(d.get("selftext") or ""),
            score=int(d.get("score") or 0),
            num_comments=int(d.get("num_comments") or 0),
            created_utc=float(d.get("created_utc") or 0),
            permalink=str(d.get("permalink") or ""),
            url=str(d.get("url") or ""),
            ingested_at=ingested,
            listing_time_filter=listing_time_filter,
            top_comments=[],
        )


class ThemeRecord(BaseModel):
    theme_id: str
    theme_label: str
    description: str
    pain_point_type: str = Field(
        default="unknown",
        description="e.g. tooling, career, architecture, incident, cost",
    )
    example_question_phrases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_post_ids: list[str] = Field(default_factory=list)
    subreddits: list[str] = Field(default_factory=list)
    taxonomy_version: str = ""
    prompt_hash: str = ""
