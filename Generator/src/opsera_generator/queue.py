"""Append SlackQueueItems to the Slack-Queue JSON file."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import SlackQueueItem

log = logging.getLogger(__name__)


def append_to_slack_queue(items: list[SlackQueueItem], queue_path: Path) -> None:
    """Read existing queue (or start fresh), append new items, write back."""
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if queue_path.exists():
        try:
            existing = json.loads(queue_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                log.warning("queue.json was not a list — resetting")
                existing = []
        except json.JSONDecodeError:
            log.warning("queue.json is malformed — resetting")
            existing = []

    new_records = [json.loads(item.model_dump_json()) for item in items]
    existing.extend(new_records)

    queue_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Appended %d items to %s (total: %d)", len(items), queue_path, len(existing))
