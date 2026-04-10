from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from .models import DocHit, ScoredCandidate, Candidate
from .settings import Settings

log = logging.getLogger(__name__)

COLLECTION = "opsera_docs"


def _get_collection(settings: Settings):
    client_chroma = chromadb.PersistentClient(
        path=str(settings.opsera_chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client_chroma.get_collection(COLLECTION)


def _embed_query(oai: OpenAI, model: str, text: str) -> list[float]:
    response = oai.embeddings.create(model=model, input=text)
    return response.data[0].embedding


def _distance_to_similarity(distance: float) -> float:
    return 1 / (1 + distance)


def _build_hits(raw: dict[str, Any]) -> list[DocHit]:
    hits: list[DocHit] = []
    ids = (raw.get("ids") or [[]])[0]
    dists = (raw.get("distances") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    for i, id in enumerate(ids):
        meta: dict[str, Any] = metas[i] if i < len(metas) and metas[i] else {}
        dist = dists[i] if i < len(dists) else 0.0
        text = docs[i] if i < len(docs) else ""
        hits.append(
            DocHit(
                chunk_id=id,
                distance=dist,
                similarity=_distance_to_similarity(dist),
                text=text,
                **meta,
            )
        )
    return hits


def _aggregate_score(hits: list[DocHit]) -> float:
    if not hits:
        return 0.0
    return sum(hit.similarity for hit in hits) / len(hits)


def _score_candidate(candidate: Candidate, settings: Settings) -> ScoredCandidate:
    collection = _get_collection(settings)
    oai = OpenAI(api_key=settings.openai_api_key)
    emb_model = settings.openai_embedding_model
    query_vec = _embed_query(oai, emb_model, candidate.text)
    raw = collection.query(query_embeddings=[query_vec], n_results=8)
    hits = _build_hits(raw)
    score = _aggregate_score(hits)
    return ScoredCandidate(id=candidate.id, text=candidate.text, similarity=score, top_hits=hits)


def score_all(candidates: list[Candidate], settings: Settings) -> list[ScoredCandidate]:
    scored = [_score_candidate(c, settings) for c in candidates]
    return sorted(scored, key=lambda x: x.similarity, reverse=True)
