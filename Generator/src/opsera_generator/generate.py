from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .models import CommentDraft
from .settings import Settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior DevOps practitioner who has spent years working in platform engineering and software delivery at scale. You also have deep, first-hand knowledge of Opsera — a Unified DevOps Intelligence Platform — because you use it to connect and govern your own toolchain.

Your task: write a Reddit comment responding to a DevOps community question or pain point. The comment will be posted by a practitioner, not a vendor.

Rules:
1. Lead with genuine, actionable technical advice. The community comes first — the comment must stand alone as useful even without any product reference.
2. In 1–2 sentences only, inject Opsera's specific, opinionated technical POV where it is directly relevant — e.g. how a specific capability solves the exact problem described. Be concrete and specific, not vague.
3. Ground every product claim strictly in the provided KB excerpts. Do not invent capabilities.
4. Never say "use Opsera" or "try Opsera". Never use marketing language like "powerful", "seamless", or "best-in-class". Speak like a practitioner sharing experience, not a sales pitch.
5. If the KB evidence is weak or tangential, keep the product reference brief or omit it entirely — a community-first answer is always better than a forced plug.
6. Target length: 150–250 words. No bullet lists unless the question clearly calls for steps.
7. Tone: direct, confident, slightly opinionated — like a senior engineer on r/devops who has seen this problem before.

Return strict JSON with exactly these keys:
{"comment_text": "...", "area": "pipelines|dora_metrics|integrations|security|analytics|general", "confidence": 0.0-1.0}
No markdown. No other keys."""


def _build_user_prompt(theme_text: str, kb_hits: list[dict[str, Any]]) -> str:
    excerpts = "\n\n".join(
        f"[Excerpt {i + 1}]\n{hit['text'][:600]}"
        for i, hit in enumerate(kb_hits[:3])
    )
    return f"Community theme / question:\n{theme_text}\n\nKB Evidence (Opsera product knowledge):\n{excerpts}"


def _call_llm(oai: OpenAI, model: str, user_prompt: str) -> dict[str, Any]:
    response = oai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data)}")
    return data


def generate_comment(
    theme_id: str,
    theme_text: str,
    kb_hits: list[dict[str, Any]],
    settings: Settings,
) -> CommentDraft:
    oai = OpenAI(api_key=settings.openai_api_key)
    user_prompt = _build_user_prompt(theme_text, kb_hits)

    try:
        result = _call_llm(oai, settings.openai_model, user_prompt)
    except Exception as e:
        log.error("LLM call failed for %s: %s", theme_id, e)
        raise

    return CommentDraft(
        theme_id=theme_id,
        comment_text=str(result.get("comment_text", "")),
        area=str(result.get("area", "general")),
        confidence=float(result.get("confidence", 0.5)),
        kb_sources=[h.get("source_path", "") for h in kb_hits[:3]],
    )
