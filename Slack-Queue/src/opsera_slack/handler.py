"""Handle Slack interactive callback payloads (approve/reject button clicks)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .models import SlackQueueItem
from .sender import send_next_to_slack
from .settings import Settings
from .store import update_item_status

log = logging.getLogger(__name__)


def verify_slack_signature(
    signing_secret: str,
    request_body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify the Slack request signature to prevent spoofed callbacks."""
    # Reject requests older than 5 minutes
    if abs(time.time() - int(timestamp)) > 300:
        log.warning("Slack request timestamp too old")
        return False

    basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _post_resolution_message(
    client: WebClient,
    channel: str,
    item: SlackQueueItem,
    action: str,
) -> None:
    """Post a follow-up message confirming the action taken."""
    if action == "approve":
        text = f"Approved — `{item.theme_id}` is ready for posting."
        emoji = "white_check_mark"
    else:
        text = f"Rejected — `{item.theme_id}` has been removed from the queue."
        emoji = "x"

    try:
        client.chat_postMessage(
            channel=channel,
            text=f":{emoji}: {text}",
        )
    except SlackApiError as e:
        log.warning("Could not post resolution message: %s", e.response["error"])


def handle_action(payload: dict, settings: Settings) -> None:
    """Process an approve or reject button click from Slack Block Kit."""
    actions = payload.get("actions", [])
    if not actions:
        log.warning("Slack payload had no actions")
        return

    action = actions[0]
    action_id: str = action.get("action_id", "")
    item_id: str = action.get("value", "")

    if action_id.startswith("approve_"):
        new_status = "approved"
        verb = "approve"
    elif action_id.startswith("reject_"):
        new_status = "rejected"
        verb = "reject"
    else:
        log.warning("Unknown action_id: %s", action_id)
        return

    updated = update_item_status(settings.queue_path, item_id, new_status)
    if not updated:
        log.error("Could not find item %s to update", item_id)
        return

    log.info("Item %s %sd via Slack", item_id, verb)

    if settings.slack_configured:
        client = WebClient(token=settings.slack_bot_token)
        _post_resolution_message(client, settings.slack_channel_id, updated, verb)
        # Automatically send the next pending item
        send_next_to_slack(settings)
