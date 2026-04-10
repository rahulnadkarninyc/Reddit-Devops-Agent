from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .models import ScoredCandidate, DocHit
from .settings import Settings

log = logging.getLogger(__name__)

CLASSIFY_SYSTEM = """You are a classifier for Opsera, a Unified DevOps Intelligence Platform.
You will receive a Reddit Question from a DevOps or engineering community, along with excerpts from Opsera's knowledge base.

Your job: decide whether this question is one Opsera could meaningfully and credibly respond to.

Rules:
    - A question is a good fit if Opsera's product directly addresses the pain point (eg pipeline orchestration, DORA metrics, tool chain integration, security gates, DevOps Visibility).
    - A question is not a good fit if it is purely about a third party tool Opsera does not touch, a career/HR topic, or too generic to add product-specific value.
    - Use the knowledge base excerpts as evidence. Do not invent product capabilities not present in the excerpts.
    - area: the Opsera product area most relevant to this question. One of: pipelines, dora_metrics, integrations, security, analytics, general, none.
    - confidence: how certain you are in the fit decision, 0.0-1.0.
    - rationale: one sentence explaining your decision, grounded in the excerpts.
    Return strict JSON with exactly these keys:
    {"fit": true or false, "confidence": 0.0-1.0, "area": "...", "rationale": "..."}
    No other keys. No markdown."""


def _build_prompt(candidate_text: str, top_chunks: list[DocHit]) -> str:
    chunks_text = "\n\n".join(
        f"[Excerpt {i + 1}]\n{hit.text}" for i, hit in enumerate(top_chunks[:3])
    )
    return f"Question:\n{candidate_text}\n\nKnowledge Base Excerpts:\n{chunks_text}"


def _call_llm(oai: OpenAI, model: str, user_prompt: str) -> dict[str, Any]:
    response = oai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from model, got: {type(data)}")
    return data


def classify(candidate: ScoredCandidate, settings: Settings) -> dict[str, Any]:
    settings = settings.resolve_paths()
    if not settings.openai_api_key:
        log.error("Set OPENAI_API_KEY")
        return {"fit": False, "confidence": 0.0, "area": "none", "rationale": "No API key configured."}
    oai = OpenAI(api_key=settings.openai_api_key)
    model = settings.openai_model
    user_prompt = _build_prompt(candidate.text, candidate.top_hits)
    return _call_llm(oai, model, user_prompt)
