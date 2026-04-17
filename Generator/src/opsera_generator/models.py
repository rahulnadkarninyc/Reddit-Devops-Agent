from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CommentDraft(BaseModel):
    theme_id: str
    comment_text: str
    area: str
    confidence: float
    kb_sources: list[str] = Field(default_factory=list)


class SlackQueueItem(BaseModel):
    item_id: str
    theme_id: str
    theme_text: str
    comment_draft: str
    area: str
    similarity: float
    generated_at: datetime
    status: Literal["pending", "sent", "skipped"] = "pending"
