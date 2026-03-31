from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from fastapi import FastAPI, HTTPException, Query
from openai import OpenAI
from pydantic import BaseModel, Field

from reddit_kb.embed_chroma import COLLECTION
from reddit_kb.settings import Settings

log = logging.getLogger(__name__)


class ThemeHit(BaseModel):
    theme_id: str
    theme_label: str
    pain_point_type: str = ""
    distance: float = Field(description="Vector distance (lower is closer)")
    document: str = ""
    subreddits: str = ""
    taxonomy_version: str = ""


class QueryResponse(BaseModel):
    query: str
    k: int
    themes: list[ThemeHit]


def search_themes(settings: Settings, q: str, k: int = 8) -> QueryResponse:
    """Retrieve top-k theme cards by embedding similarity (for API and CLI)."""
    settings = settings.resolve_paths()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    if not settings.chroma_path.exists():
        raise FileNotFoundError("Chroma store missing; run reddit-kb-embed")

    client_chroma = chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    try:
        coll = client_chroma.get_collection(COLLECTION)
    except Exception as e:
        raise FileNotFoundError("Theme collection missing; run reddit-kb-embed") from e

    oai = OpenAI(api_key=settings.openai_api_key)
    emb = oai.embeddings.create(
        model=settings.openai_embedding_model,
        input=q,
    )
    vec = emb.data[0].embedding
    raw = coll.query(query_embeddings=[vec], n_results=k)
    hits: list[ThemeHit] = []
    ids = (raw.get("ids") or [[]])[0]
    dists = (raw.get("distances") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    for i, tid in enumerate(ids):
        meta: dict[str, Any] = metas[i] if i < len(metas) and metas[i] else {}
        dist = dists[i] if i < len(dists) else 0.0
        doc = docs[i] if i < len(docs) else ""
        hits.append(
            ThemeHit(
                theme_id=str(tid),
                theme_label=str(meta.get("theme_label") or ""),
                pain_point_type=str(meta.get("pain_point_type") or ""),
                distance=float(dist),
                document=str(doc or ""),
                subreddits=str(meta.get("subreddits") or ""),
                taxonomy_version=str(meta.get("taxonomy_version") or ""),
            )
        )
    return QueryResponse(query=q, k=k, themes=hits)


def create_app(settings: Settings) -> FastAPI:
    settings = settings.resolve_paths()
    app = FastAPI(title="Reddit KB", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/query", response_model=QueryResponse)
    def query_kb(
        q: str = Query(..., min_length=1, description="Natural language query"),
        k: int = Query(8, ge=1, le=50),
    ) -> QueryResponse:
        if not settings.openai_api_key:
            raise HTTPException(503, "OPENAI_API_KEY not configured")
        try:
            return search_themes(settings, q, k=k)
        except FileNotFoundError as e:
            raise HTTPException(503, str(e)) from e
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from e

    return app
