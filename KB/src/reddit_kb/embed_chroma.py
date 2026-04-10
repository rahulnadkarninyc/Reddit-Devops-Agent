from __future__ import annotations

import json
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from reddit_kb.models import ThemeRecord
from reddit_kb.settings import Settings

log = logging.getLogger(__name__)

COLLECTION = "theme_cards"


def _theme_document(t: ThemeRecord) -> str:
    phrases = " ".join(t.example_question_phrases)
    return f"{t.theme_label}\n{t.description}\n{t.pain_point_type}\n{phrases}"


def load_themes_json(path: Path) -> tuple[str, str, list[ThemeRecord]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    tv = str(data.get("taxonomy_version") or "")
    ph = str(data.get("prompt_hash") or "")
    raw = data.get("themes")
    if not isinstance(raw, list):
        return tv, ph, []
    records = []
    for item in raw:
        if isinstance(item, dict):
            records.append(ThemeRecord.model_validate(item))
    return tv, ph, records


def run_embed(settings: Settings) -> int:
    settings = settings.resolve_paths()
    if not settings.openai_api_key:
        log.error("Set OPENAI_API_KEY")
        return 1

    themes_path = settings.reddit_kb_root / "data" / "themes" / "themes.json"
    if not themes_path.exists():
        log.error("Missing %s; run reddit-kb-themes first", themes_path)
        return 1

    taxonomy_version, prompt_hash, themes = load_themes_json(themes_path)
    if not themes:
        log.error("No themes in file")
        return 1

    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    client_chroma = chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    oai = OpenAI(api_key=settings.openai_api_key)
    emb_model = settings.openai_embedding_model

    try:
        client_chroma.delete_collection(COLLECTION)
    except Exception:
        pass
    coll = client_chroma.create_collection(
        name=COLLECTION,
        metadata={"description": "DevOps Reddit theme cards"},
    )

    docs = [_theme_document(t) for t in themes]
    ids = [t.theme_id for t in themes]
    metadatas = [
        {
            "theme_label": t.theme_label[:512],
            "pain_point_type": t.pain_point_type[:128],
            "taxonomy_version": taxonomy_version or t.taxonomy_version,
            "prompt_hash": prompt_hash or t.prompt_hash,
            "subreddits": ",".join(t.subreddits)[:1024],
            "source_post_count": len(t.source_post_ids),
        }
        for t in themes
    ]

    batch = 64
    for i in range(0, len(docs), batch):
        chunk_docs = docs[i : i + batch]
        chunk_ids = ids[i : i + batch]
        chunk_meta = metadatas[i : i + batch]
        r = oai.embeddings.create(model=emb_model, input=chunk_docs)
        vectors = [d.embedding for d in r.data]
        coll.add(
            ids=chunk_ids,
            embeddings=vectors,
            documents=chunk_docs,
            metadatas=chunk_meta,
        )
        log.info("Embedded %s-%s / %s", i, i + len(chunk_docs), len(docs))

    log.info("Chroma collection %s ready at %s", COLLECTION, settings.chroma_path)
    return 0
