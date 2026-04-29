"""FastAPI application: GUI dashboard + REST API + Slack interactive webhook."""
from __future__ import annotations

import json
import logging
import urllib.parse
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


# ── GUI routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, tab: str = "pending"):
    items = load_queue(settings.queue_path)
    stats = queue_stats(settings.queue_path)
    pending = [i for i in items if i.status == "pending"]
    sent = [i for i in items if i.status == "sent_to_slack"]
    history = list(reversed([i for i in items if i.status in ("approved", "rejected")]))
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
        raise HTTPException(status_code=400, detail="human_response cannot be empty — write your own comment before approving")
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


@app.post("/api/send-next")
async def api_send_next():
    if not settings.slack_configured:
        raise HTTPException(
            status_code=400,
            detail="Slack not configured. Set SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, and SLACK_SIGNING_SECRET in .env",
        )
    item = send_next_to_slack(settings)
    if not item:
        return {"sent": False, "message": "No pending items or one is already in-flight"}
    return {"sent": True, "item_id": item.item_id, "theme_id": item.theme_id}


@app.get("/api/stats")
async def api_stats():
    return queue_stats(settings.queue_path)


# ── Slack interactive webhook ─────────────────────────────────────────────────

@app.post("/slack/actions")
async def slack_actions(request: Request):
    body_bytes = await request.body()

    if settings.slack_signing_secret:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
        signature = request.headers.get("X-Slack-Signature", "")
        if not verify_slack_signature(settings.slack_signing_secret, body_bytes, timestamp, signature):
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
    print()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
