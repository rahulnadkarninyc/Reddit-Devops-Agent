"""FastAPI application: GUI dashboard + REST API + Slack interactive webhook."""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .handler import handle_action, verify_slack_signature
from .models import SlackQueueItem
from .sender import send_next_to_slack
from .settings import Settings
from .store import (
    get_item,
    get_last_sent_at,
    load_queue,
    queue_stats,
    submit_human_response,
    update_item_status,
)

log = logging.getLogger(__name__)

settings = Settings()

app = FastAPI(title="Opsera Reddit Comment Queue", docs_url=None, redoc_url=None)

_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


# ── Background watcher ────────────────────────────────────────────────────────

async def _queue_watcher() -> None:
    """Poll queue every 60 s and auto-dispatch the next pending item to Slack."""
    await asyncio.sleep(5)  # short initial delay to let the server finish starting
    while True:
        try:
            if settings.slack_configured:
                send_next_to_slack(settings)
        except Exception as e:
            log.error("Watcher error: %s", e)
        await asyncio.sleep(60)


@app.on_event("startup")
async def start_watcher() -> None:
    asyncio.create_task(_queue_watcher())
    log.info("Queue watcher started (poll interval: 60s, rate limit: %dm)", settings.min_send_interval_minutes)


# ── GUI routes ────────────────────────────────────────────────────────────────

def _queue_status_label(queue_path: Path, min_interval_minutes: int) -> str:
    """Human-readable status for the dashboard header."""
    from .store import load_queue as lq
    items = lq(queue_path)
    in_flight = any(i.status == "sent_to_slack" for i in items)
    if in_flight:
        return "Waiting for action in Slack"
    pending_count = sum(1 for i in items if i.status == "pending")
    if pending_count == 0:
        return "Queue empty"
    last_sent = get_last_sent_at(queue_path)
    if last_sent:
        elapsed = (datetime.now(timezone.utc) - last_sent).total_seconds()
        remaining = max(0, int((min_interval_minutes * 60 - elapsed) / 60))
        if remaining > 0:
            return f"Next send in ~{remaining}m"
    return f"{pending_count} item(s) ready — sending soon"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, tab: str = "pending"):
    items = load_queue(settings.queue_path)
    stats = queue_stats(settings.queue_path)
    pending = [i for i in items if i.status == "pending"]
    sent = [i for i in items if i.status == "sent_to_slack"]
    history = list(reversed([i for i in items if i.status in ("approved", "rejected")]))
    status_label = _queue_status_label(settings.queue_path, settings.min_send_interval_minutes)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "tab": tab,
            "pending": pending,
            "sent": sent,
            "history": history,
            "stats": stats,
            "slack_configured": settings.slack_configured,
            "queue_status_label": status_label,
        },
    )


# ── REST API ──────────────────────────────────────────────────────────────────

@app.get("/api/items")
async def get_items(status: Optional[str] = None):
    items = load_queue(settings.queue_path)
    if status:
        items = [i for i in items if i.status == status]
    return [json.loads(i.model_dump_json()) for i in items]


@app.get("/api/items/{item_id}")
async def get_single_item(item_id: str):
    item = get_item(settings.queue_path, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return json.loads(item.model_dump_json())


class SubmitResponse(BaseModel):
    human_response: str


@app.post("/api/items/{item_id}/approve")
async def approve_item(item_id: str, body: SubmitResponse):
    if not body.human_response.strip():
        raise HTTPException(
            status_code=400,
            detail="human_response cannot be empty — write your own comment before approving",
        )
    try:
        updated = submit_human_response(settings.queue_path, item_id, body.human_response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "approved", "item_id": item_id}


@app.post("/api/items/{item_id}/reject")
async def reject_item(item_id: str):
    updated = update_item_status(settings.queue_path, item_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "rejected", "item_id": item_id}


@app.post("/api/internal/trigger")
async def internal_trigger():
    """Internal endpoint for the Generator to nudge the watcher immediately after writing to queue."""
    if not settings.slack_configured:
        return {"triggered": False, "reason": "Slack not configured"}
    item = send_next_to_slack(settings)
    if item:
        return {"triggered": True, "item_id": item.item_id}
    return {"triggered": False, "reason": "Rate-limited, in-flight, or no pending items"}


@app.get("/api/stats")
async def api_stats():
    stats = queue_stats(settings.queue_path)
    last_sent = get_last_sent_at(settings.queue_path)
    return {
        **stats,
        "queue_status": _queue_status_label(settings.queue_path, settings.min_send_interval_minutes),
        "last_sent_at": last_sent.isoformat() if last_sent else None,
    }


# ── Slack interactive webhook ─────────────────────────────────────────────────

@app.post("/slack/actions")
async def slack_actions(request: Request):
    body_bytes = await request.body()

    if settings.slack_signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
        signature = request.headers.get("X-Slack-Signature", "")
        if not verify_slack_signature(
            settings.slack_signing_secret, body_bytes, timestamp, signature
        ):
            raise HTTPException(status_code=403, detail="Invalid Slack signature")

    body_str = body_bytes.decode("utf-8")
    parsed = urllib.parse.parse_qs(body_str)
    payload_str = parsed.get("payload", ["{}"])[0]
    payload = json.loads(payload_str)

    try:
        handle_action(payload, settings)
    except Exception as e:
        log.error("Error handling Slack action: %s", e)

    return Response(status_code=200)


# ── Server entry point ────────────────────────────────────────────────────────

def serve() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"\n  Opsera Comment Queue Dashboard")
    print(f"  Open: http://{settings.host}:{settings.port}")
    if not settings.slack_configured:
        print(f"  Slack: not configured (GUI-only mode)")
    else:
        print(f"  Slack: configured — channel {settings.slack_channel_id}")
        print(f"  Rate limit: {settings.min_send_interval_minutes}m between sends")
    print()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
