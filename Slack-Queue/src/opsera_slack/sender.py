"""Build and send Block Kit messages to Slack, one item at a time."""
from __future__ import annotations

import logging
import sys

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .models import SlackQueueItem
from .settings import Settings
from .store import get_next_pending, update_item_status

log = logging.getLogger(__name__)


def build_block_kit_message(item: SlackQueueItem) -> list[dict]:
    area_label = item.area_label()
    score_pct = int(item.similarity * 100)

    # Truncate theme text for the header
    theme_preview = item.theme_text[:120] + ("..." if len(item.theme_text) > 120 else "")

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Reddit Comment Draft — {area_label}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Theme:*\n{theme_preview}"},
                {"type": "mrkdwn", "text": f"*Area:* {area_label}\n*Relevance:* {score_pct}%"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Proposed comment:*\n\n{item.comment_draft}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": f"approve_{item.item_id}",
                    "value": item.item_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Approve this comment?"},
                        "text": {"type": "plain_text", "text": "This will mark it as approved and ready for posting."},
                        "confirm": {"type": "plain_text", "text": "Yes, approve"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": f"reject_{item.item_id}",
                    "value": item.item_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Reject this comment?"},
                        "text": {"type": "plain_text", "text": "This will mark it as rejected and move to the next item."},
                        "confirm": {"type": "plain_text", "text": "Yes, reject"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Item ID: `{item.item_id}` | Generated: {item.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
                }
            ],
        },
    ]


def send_next_to_slack(settings: Settings) -> SlackQueueItem | None:
    """Send the next pending item to Slack. Returns the sent item or None."""
    if not settings.slack_configured:
        log.warning("Slack not configured — set SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SLACK_SIGNING_SECRET")
        return None

    item = get_next_pending(settings.queue_path)
    if not item:
        log.info("No pending items to send (queue empty or item already in-flight)")
        return None

    client = WebClient(token=settings.slack_bot_token)
    blocks = build_block_kit_message(item)

    try:
        client.chat_postMessage(
            channel=settings.slack_channel_id,
            blocks=blocks,
            text=f"Reddit comment draft for review: {item.theme_id}",
        )
        update_item_status(settings.queue_path, item.item_id, "sent_to_slack")
        log.info("Sent item %s to Slack channel %s", item.item_id, settings.slack_channel_id)
        return item
    except SlackApiError as e:
        log.error("Slack API error: %s", e.response["error"])
        return None


def send_cli() -> None:
    """CLI entry point: opsera-slack-send"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    item = send_next_to_slack(settings)
    if item:
        print(f"Sent to Slack: [{item.area}] {item.theme_id}")
    else:
        print("Nothing sent — check logs above.")
    sys.exit(0)
