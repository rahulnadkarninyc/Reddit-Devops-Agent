"""Entry point: poll pending inbox, generate comments, write to Slack queue."""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request as URLRequest
from urllib.request import urlopen
from urllib.error import URLError

from .generate import generate_comment
from .models import SlackQueueItem
from .queue import append_to_slack_queue
from .settings import Settings

log = logging.getLogger(__name__)


def _load_plan(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _process_plan(plan_path: Path, settings: Settings) -> list[SlackQueueItem]:
    plan = _load_plan(plan_path)
    candidates = plan.get("selected_candidates", [])
    if not candidates:
        log.warning("Plan %s has no selected_candidates — skipping", plan_path.name)
        return []

    items: list[SlackQueueItem] = []
    for candidate in candidates:
        theme_id = candidate.get("id", "unknown")
        theme_text = candidate.get("text", "")
        similarity = float(candidate.get("similarity", 0.0))
        top_hits = candidate.get("top_hits", [])

        log.info("Generating comment for %s ...", theme_id)
        try:
            draft = generate_comment(
                theme_id=theme_id,
                theme_text=theme_text,
                kb_hits=top_hits,
                settings=settings,
            )
        except Exception as e:
            log.error("Skipping %s due to generation error: %s", theme_id, e)
            continue

        items.append(
            SlackQueueItem(
                item_id=str(uuid.uuid4()),
                theme_id=theme_id,
                theme_text=theme_text,
                comment_draft=draft.comment_text,
                area=draft.area,
                similarity=similarity,
                generated_at=datetime.now(timezone.utc),
                status="pending",
            )
        )
        print(f"\n  [{draft.area}] {theme_id}")
        print(f"  confidence={draft.confidence:.2f}  similarity={similarity:.3f}")
        print(f"  ---")
        print(f"  {draft.comment_text[:300]}{'...' if len(draft.comment_text) > 300 else ''}")

    return items


def run_generator(
    inbox_path: Path,
    slack_queue_path: Path,
    settings: Settings,
) -> int:
    pending_files = sorted(inbox_path.glob("*_plan.json"))
    if not pending_files:
        print(f"No pending plans in {inbox_path}")
        return 0

    processed_dir = inbox_path.parent / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    total_items = 0
    for plan_path in pending_files:
        print(f"\nProcessing {plan_path.name} ...")
        items = _process_plan(plan_path, settings)

        if items:
            append_to_slack_queue(items, slack_queue_path)
            total_items += len(items)

        dest = processed_dir / plan_path.name
        shutil.move(str(plan_path), str(dest))
        log.info("Moved %s → processed/", plan_path.name)

    print(f"\n{total_items} comment drafts written to {slack_queue_path}")

    if total_items > 0:
        _nudge_slack_server()

    return 0


def _nudge_slack_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Tell the Slack dashboard server to try dispatching the next item immediately."""
    url = f"http://{host}:{port}/api/internal/trigger"
    try:
        req = URLRequest(url, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            if body.get("triggered"):
                print(f"  Slack: dispatched item {body.get('item_id', '')[:8]} immediately")
            else:
                print(f"  Slack: {body.get('reason', 'watcher will pick it up within 60s')}")
    except URLError:
        log.debug("Slack server not reachable at %s — watcher will dispatch within 60s", url)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    p = argparse.ArgumentParser(description="Generate Reddit comments from action plan queue")
    p.add_argument(
        "--inbox",
        type=Path,
        default=None,
        help="Path to pending/ inbox dir (default: from .env / Settings)",
    )
    p.add_argument(
        "--slack-queue",
        type=Path,
        default=None,
        help="Path to Slack-Queue/queue.json (default: from .env / Settings)",
    )
    args = p.parse_args()

    settings = Settings().resolve_paths()

    inbox = args.inbox or settings.inbox_path
    slack_queue = args.slack_queue or settings.slack_queue_path

    if not inbox.exists():
        print(f"Inbox does not exist: {inbox}")
        return

    sys.exit(run_generator(inbox, slack_queue, settings))


if __name__ == "__main__":
    main()
