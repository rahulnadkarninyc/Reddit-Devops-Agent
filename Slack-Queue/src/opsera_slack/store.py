"""Single source of truth for reading and writing queue.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import ItemStatus, SlackQueueItem

log = logging.getLogger(__name__)


def load_queue(path: Path) -> list[SlackQueueItem]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [SlackQueueItem.model_validate(r) for r in raw]
    except Exception as e:
        log.error("Failed to load queue from %s: %s", path, e)
        return []


def save_queue(path: Path, items: list[SlackQueueItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(item.model_dump_json()) for item in items]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def get_item(path: Path, item_id: str) -> SlackQueueItem | None:
    for item in load_queue(path):
        if item.item_id == item_id:
            return item
    return None


def update_item_status(path: Path, item_id: str, status: ItemStatus) -> SlackQueueItem | None:
    items = load_queue(path)
    for i, item in enumerate(items):
        if item.item_id == item_id:
            items[i] = item.model_copy(update={"status": status})
            save_queue(path, items)
            log.info("Item %s → %s", item_id, status)
            return items[i]
    log.warning("Item %s not found in queue", item_id)
    return None


def submit_human_response(
    path: Path, item_id: str, human_response: str
) -> SlackQueueItem | None:
    """Save the human-written response and mark the item as approved."""
    if not human_response.strip():
        raise ValueError("human_response cannot be empty")
    items = load_queue(path)
    for i, item in enumerate(items):
        if item.item_id == item_id:
            items[i] = item.model_copy(
                update={"human_response": human_response, "status": "approved"}
            )
            save_queue(path, items)
            log.info("Item %s approved with human response (%d chars)", item_id, len(human_response))
            return items[i]
    log.warning("Item %s not found in queue", item_id)
    return None


def get_next_pending(path: Path) -> SlackQueueItem | None:
    """Return the oldest pending item, but only if nothing is already in-flight."""
    items = load_queue(path)
    in_flight = any(item.status == "sent_to_slack" for item in items)
    if in_flight:
        return None
    for item in items:
        if item.status == "pending":
            return item
    return None


def queue_stats(path: Path) -> dict[str, int]:
    items = load_queue(path)
    counts: dict[str, int] = {"pending": 0, "sent_to_slack": 0, "approved": 0, "rejected": 0}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts
