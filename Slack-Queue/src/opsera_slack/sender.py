"""Build and send Block Kit messages to Slack."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .models import SlackQueueItem
from .store import get_next_pending, update_item_status

if TYPE_CHECKING:
    from .settings import Settings

log = logging.getLogger(__name__)


def build_block_kit_message(item: SlackQueueItem) -> list[dict]:
    """Build a Slack Block Kit message for a pending comment.

    The Approve button is replaced with a 'Write Response' button that opens
    a modal so the human must consciously author their own reply.
    """
    area_label = item.area_label()
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Reddit Comment Review", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Area:* {area_label}"},
                {"type": "mrkdwn", "text": f"*Similarity:* {item.similarity:.0%}"},
                {"type": "mrkdwn", "text": f"*Theme:* {item.theme_text[:120]}"},
                {"type": "mrkdwn", "text": f"*ID:* `{item.item_id[:8]}…`"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*AI Suggestion — for reference only:*\n```{item.comment_draft[:2800]}```",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_Write your own response in the modal below. The AI suggestion will not be posted._",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Write Response", "emoji": True},
                    "style": "primary",
                    "action_id": f"open_modal_{item.item_id}",
                    "value": item.item_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": f"reject_{item.item_id}",
                    "value": item.item_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Reject comment?"},
                        "text": {"type": "plain_text", "text": "This will remove the item from the queue."},
                        "confirm": {"type": "plain_text", "text": "Yes, reject"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
            ],
        },
    ]


def build_response_modal(item: SlackQueueItem) -> dict:
    """Build the Slack modal view that lets the human write their own comment."""
    return {
        "type": "modal",
        "callback_id": f"submit_response_{item.item_id}",
        "title": {"type": "plain_text", "text": "Write Your Response"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*AI Suggestion — for reference only:*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{item.comment_draft[:2800]}```",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "human_response_block",
                "label": {
                    "type": "plain_text",
                    "text": "Your response (write from scratch — this is what will be posted)",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "human_response_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Write your own comment here. The AI suggestion is for reference only and will not be posted.",
                    },
                    "min_length": 1,
                },
            },
        ],
    }


def send_next_to_slack(settings: "Settings") -> SlackQueueItem | None:
    """Pull the oldest pending item, send it to Slack, and mark it as in-flight."""
    item = get_next_pending(settings.queue_path)
    if not item:
        log.info("No pending item to send")
        return None

    client = WebClient(token=settings.slack_bot_token)
    try:
        client.chat_postMessage(
            channel=settings.slack_channel_id,
            blocks=build_block_kit_message(item),
            text=f"New Reddit comment ready for review (ID: {item.item_id[:8]})",
        )
        update_item_status(settings.queue_path, item.item_id, "sent_to_slack")
        log.info("Sent item %s to Slack channel %s", item.item_id, settings.slack_channel_id)
        return item
    except SlackApiError as e:
        log.error("Slack API error: %s", e.response["error"])
        return None


def send_cli() -> None:
    """CLI entry point: send next pending item to Slack."""
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    from .settings import Settings as S
    s = S()
    if not s.slack_configured:
        print("Slack not configured — set SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SLACK_SIGNING_SECRET in .env")
        sys.exit(1)
    item = send_next_to_slack(s)
    if item:
        print(f"Sent item {item.item_id} to Slack")
    else:
        print("Nothing to send or Slack error")
        sys.exit(1)
