from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ItemStatus = Literal["pending", "sent_to_slack", "approved", "rejected"]

AREA_LABELS: dict[str, str] = {
    "pipelines": "Pipelines",
    "dora_metrics": "DORA Metrics",
    "integrations": "Integrations",
    "security": "Security",
    "analytics": "Analytics",
    "general": "General",
}

AREA_COLORS: dict[str, str] = {
    "pipelines": "blue",
    "dora_metrics": "purple",
    "integrations": "teal",
    "security": "red",
    "analytics": "orange",
    "general": "gray",
}


class SlackQueueItem(BaseModel):
    item_id: str
    theme_id: str
    theme_text: str
    comment_draft: str
    area: str
    similarity: float
    generated_at: datetime
    status: ItemStatus = "pending"

    def area_label(self) -> str:
        return AREA_LABELS.get(self.area, self.area.title())

    def area_color(self) -> str:
        return AREA_COLORS.get(self.area, "gray")
