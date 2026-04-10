from pathlib import Path
import hashlib
import logging
import sys

import chromadb
from chromadb.config import Settings as ChromaSettings
from dotenv import load_dotenv
from langchain_text_splitters import CharacterTextSplitter
from openai import OpenAI

from .models import OpsDoc
from .settings import Settings

log = logging.getLogger(__name__)

load_dotenv()

COLLECTION = "opsera_docs"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return text_splitter.split_text(text)


def make_chunk_id(file_path: Path, chunk_index: int) -> str:
    raw = f"{file_path.resolve()}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()


def detect_doc_type(file_path: Path) -> str:
    parent = file_path.parent.name
    if parent in ("product", "tech", "messaging"):
        return parent
    return "general"


def load_docs(kb_root: Path) -> list[OpsDoc]:
    all_chunks: list[OpsDoc] = []

    for file_path in kb_root.rglob("*.md"):
        text = file_path.read_text(encoding="utf-8")
        if not text:
            continue

        doc_type = detect_doc_type(file_path)
        source_path = str(file_path.relative_to(kb_root))
        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

        for i, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(file_path, i)
            all_chunks.append(
                OpsDoc(
                    chunk_id=chunk_id,
                    source_path=source_path,
                    doc_type=doc_type,
                    text=chunk,
                    chunk_index=i,
                )
            )

    return all_chunks


def run_ingest(settings: Settings) -> int:
    settings = settings.resolve_paths()

    if not settings.openai_api_key:
        log.error("Set OPENAI_API_KEY")
        return 1

    if not settings.opsera_kb_root.exists():
        log.error("OPSERA_KB_ROOT does not exist: %s", settings.opsera_kb_root)
        return 1

    docs: list[OpsDoc] = load_docs(settings.opsera_kb_root)
    if not docs:
        log.error("No .md files found under %s", settings.opsera_kb_root)
        return 1
    log.info("Loaded %s chunks from %s", len(docs), settings.opsera_kb_root)

    settings.opsera_chroma_path.mkdir(parents=True, exist_ok=True)
    client_chroma = chromadb.PersistentClient(
        path=str(settings.opsera_chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    coll = client_chroma.get_or_create_collection(
        name=COLLECTION,
        metadata={"description": "Opsera internal KB chunks"},
    )

    oai = OpenAI(api_key=settings.openai_api_key)
    emb_model = settings.openai_embedding_model

    batch_size = 64

    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]

        texts = [d.text for d in batch]
        ids = [d.chunk_id for d in batch]
        metadatas = [
            {
                "source_path": d.source_path,
                "doc_type": d.doc_type,
                "chunk_index": d.chunk_index,
            }
            for d in batch
        ]
        response = oai.embeddings.create(model=emb_model, input=texts)
        vectors = [item.embedding for item in response.data]

        coll.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        log.info("Upserted batch %s-%s / %s", i, i + len(batch), len(docs))

    log.info("Opsera KB indexed: %s chunks at %s", len(docs), settings.opsera_chroma_path)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    sys.exit(run_ingest(settings))


if __name__ == "__main__":
    main()
