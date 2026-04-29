"""Handle incoming Slack interactive payloads (button clicks, modal submissions)."""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import TYPE_CHECKING

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .sender import build_response_modal, send_next_to_slack
from .store import get_item, submit_human_response, update_item_status

if TYPE_CHECKING:
    from .settings import Settings

log = logging.getLogger(__name__)


def verify_slack_signature(
    signing_secret: str, body_bytes: bytes, timestamp: str, signature: str
) -> bool:
    """Verify that the request really came from Slack."""
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except ValueError:
        return False

    base = f"v0:{timestamp}:{body_bytes.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _post_resolution_message(
    client: WebClient,
    channel_id: str,
    item_id: str,
    action: str,
    human_response: str = "",
) -> None:
    """Post a summary message to the channel after a human decision."""
    if action == "approved":
        text = (
            f":white_check_mark: *Comment approved* (ID `{item_id[:8]}`).\n"
            + (f"*Your response:*\n```{human_response[:2000]}```" if human_response else "")
        )
    else:
        text = f":x: Comment rejected (ID `{item_id[:8]}`)."

    try:
        client.chat_postMessage(channel=channel_id, text=text)
    except SlackApiError as e:
        log.warning("Could not post resolution message: %s", e.response["error"])


def handle_action(payload: dict, settings: "Settings") -> None:
    """Route Slack interactive payloads to the appropriate handler."""
    callback_type = payload.get("type")
    client = WebClient(token=settings.slack_bot_token)

    # ── Modal submission ─────────────────────────────────────────────────────
    if callback_type == "view_submission":
        view = payload.get("view", {})
        cb_id = view.get("callback_id", "")
        if cb_id.startswith("submit_response_"):
            item_id = cb_id[len("submit_response_"):]
            state = view.get("state", {}).get("values", {})
            human_text = (
                state.get("human_response_block", {})
                .get("human_response_input", {})
                .get("value", "")
                or ""
            )
            if not human_text.strip():
                log.warning("Empty human response submitted for item %s", item_id)
                return

            updated = submit_human_response(settings.queue_path, item_id, human_text)
            if updated:
                _post_resolution_message(
                    client, settings.slack_channel_id, item_id, "approved", human_text
                )
                # Advance the queue
                send_next_to_slack(settings)
        return

    # ── Block actions (button clicks) ────────────────────────────────────────
    if callback_type == "block_actions":
        actions = payload.get("actions", [])
        trigger_id = payload.get("trigger_id", "")

        for action in actions:
            action_id: str = action.get("action_id", "")
            value: str = action.get("value", "")

            # Open Write-Response modal
            if action_id.startswith("open_modal_"):
                item_id = action_id[len("open_modal_"):]
                item = get_item(settings.queue_path, item_id)
                if not item:
                    log.warning("Item %s not found for modal open", item_id)
                    continue
                modal = build_response_modal(item)
                try:
                    client.views_open(trigger_id=trigger_id, view=modal)
                except SlackApiError as e:
                    log.error("Failed to open modal: %s", e.response["error"])

            # Reject button
            elif action_id.startswith("reject_"):
                item_id = action_id[len("reject_"):]
                updated = update_item_status(settings.queue_path, item_id, "rejected")
                if updated:
                    _post_resolution_message(
                        client, settings.slack_channel_id, item_id, "rejected"
                    )
                    send_next_to_slack(settings)
