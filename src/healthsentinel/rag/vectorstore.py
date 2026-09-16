"""Chroma-backed vector store for the medical-document RAG agent."""
from __future__ import annotations

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .. import config
from .ingestion import load_all

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "health_sentinel_medical_docs"
_store: Chroma | None = None


def get_vectorstore() -> Chroma:
    global _store
    if _store is not None:
        return _store
    embeddings = OpenAIEmbeddings(model=config.MODELS.embedding)
    _store = Chroma(
        collection_name=_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.PATHS.chroma_dir),
    )
    return _store


def build_index(docs_dir: Path | None = None, force: bool = False) -> int:
    """(Re)index medical docs into Chroma. Returns number of chunks indexed."""
    store = get_vectorstore()
    if force:
        try:
            existing = store.get()
            if existing.get("ids"):
                store.delete(ids=existing["ids"])
        except Exception as e:
            logger.warning("build_index(force=True) could not clear existing index: %s", e)
    docs_dir = docs_dir or config.PATHS.medical_docs_dir
    chunks = load_all(docs_dir)
    if not chunks:
        return 0
    ids = [f"{c.metadata.get('source_file', 'doc')}::{c.metadata.get('section_path', 'root')}::{i}"
           for i, c in enumerate(chunks)]
    texts = [c.text for c in chunks]
    # Store the chunk id inside metadata so retrieval can cite the exact chunk
    # (review §6 — citations tied to real chunk IDs).
    metadatas = [{**c.metadata, "chunk_id": ids[i]} for i, c in enumerate(chunks)]
    store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    return len(chunks)


def index_user_document(user_id: str, text: str, source_file: str) -> int:
    """Index one ad-hoc uploaded "health report" into the same store used by
    the seeded corpus, tagged with `user_id` so `retrieval.retrieve`'s
    per-user filter picks it up on the very next run. Persists across runs
    (unlike the rest of the day-end staging queue, which is discarded)."""
    from .ingestion import Chunk, _split_sections

    store = get_vectorstore()
    chunks: list[Chunk] = [
        Chunk(text=section_text, metadata={"source_file": source_file, "section_path": section_path, "user_id": user_id})
        for section_path, section_text in _split_sections(text)
    ] or [Chunk(text=text, metadata={"source_file": source_file, "section_path": "(root)", "user_id": user_id})]
    ids = [f"{source_file}::{c.metadata['section_path']}::{i}" for i, c in enumerate(chunks)]
    texts = [c.text for c in chunks]
    metadatas = [{**c.metadata, "chunk_id": ids[i]} for i, c in enumerate(chunks)]
    store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    return len(chunks)


def delete_user_documents(user_id: str) -> int:
    """Remove every chunk belonging to one user (review §6 — consent
    withdrawal / right-to-be-forgotten). Returns the number of chunks deleted."""
    store = get_vectorstore()
    existing = store.get(where={"user_id": user_id})
    ids = existing.get("ids") or []
    if ids:
        store.delete(ids=ids)
    return len(ids)


def delete_document(source_file: str) -> int:
    """Remove every chunk from one source document (review §6 — the index must
    handle document deletion). Returns the number of chunks deleted."""
    store = get_vectorstore()
    existing = store.get(where={"source_file": source_file})
    ids = existing.get("ids") or []
    if ids:
        store.delete(ids=ids)
    return len(ids)
