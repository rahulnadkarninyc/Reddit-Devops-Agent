from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OpsDoc(BaseModel):
    chunk_id: str
    source_path: str
    doc_type: str
    text: str
    chunk_index: int


class DocHit(BaseModel):
    chunk_id: str
    source_path: str
    text: str
    doc_type: str
    distance: float
    similarity: float = Field(description="1 / (1 + distance), range 0-1")


class Candidate(BaseModel):
    id: str
    text: str


class ScoredCandidate(BaseModel):
    id: str
    top_hits: list[DocHit] = Field(default_factory=list)
    text: str
    similarity: float


class ActionPlan(BaseModel):
    selected_candidates: list[ScoredCandidate]
    timestamp: datetime
