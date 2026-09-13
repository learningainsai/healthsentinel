"""Section-aware, token-bounded ingestion for medical markdown documents.

Mirrors OrgPolicyChatBot's design: split by heading structure first (so a
policy/medical section stays intact for citation-quality grounding), and only
fall back to token-bounded recursive splitting when a single section would
overflow the embedding model's practical context.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)

SECTION_MAX_TOKENS = 400
FALLBACK_CHUNK_TOKENS = 250
FALLBACK_OVERLAP_TOKENS = 40

_encoding = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw
    fm_block, body = match.group(1), match.group(2)
    metadata: dict = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, body


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Returns [(section_path, section_text), ...] preserving heading hierarchy."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [("(root)", body.strip())] if body.strip() else []

    sections: list[tuple[str, str]] = []
    path_stack: list[str] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[start:end].strip()

        path_stack = path_stack[: level - 1]
        path_stack.append(title)
        section_path = " > ".join(path_stack)
        if text:
            sections.append((section_path, text))
    return sections


def load_and_chunk(doc_path: Path) -> list[Chunk]:
    raw = doc_path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(raw)
    metadata["source_file"] = doc_path.name

    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=FALLBACK_CHUNK_TOKENS * 4,  # approx chars-per-token
        chunk_overlap=FALLBACK_OVERLAP_TOKENS * 4,
    )

    chunks: list[Chunk] = []
    for section_path, section_text in _split_sections(body):
        section_meta = {**metadata, "section_path": section_path}
        if _count_tokens(section_text) <= SECTION_MAX_TOKENS:
            chunks.append(Chunk(text=section_text, metadata=section_meta))
        else:
            for piece in fallback_splitter.split_text(section_text):
                chunks.append(Chunk(text=piece, metadata=section_meta))
    return chunks


def load_all(docs_dir: Path) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        all_chunks.extend(load_and_chunk(path))
    return all_chunks
