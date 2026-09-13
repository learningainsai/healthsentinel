"""Hybrid retrieval (dense + lexical overlap) + lightweight rerank + refusal.

A full RRF/Haystack fusion pipeline (as in OrgPolicyChatBot) is overkill for a
handful of per-user medical documents; this keeps the same *shape* — dense
candidates, a lexical signal, fused reranking, and an explicit refusal path
when evidence is too weak — at a complexity level appropriate for this corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .vectorstore import get_vectorstore

REFUSAL_MIN_SCORE = 0.28


@dataclass
class RetrievedChunk:
    text: str
    metadata: dict
    score: float


def _lexical_overlap(query: str, text: str) -> float:
    q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    t_terms = set(re.findall(r"[a-z0-9]+", text.lower()))
    if not q_terms:
        return 0.0
    return len(q_terms & t_terms) / len(q_terms)


def retrieve(query: str, user_id: str | None = None, k: int = 4) -> tuple[list[RetrievedChunk], bool]:
    """Returns (ranked_chunks, refused). refused=True when evidence is too weak
    to answer safely (guardrails doc §5 — Medical Agent failure -> reduce
    confidence / continue without medical context, never fabricate).

    `user_id`, when given, restricts the search to that user's own documents
    (Chroma metadata filter) — without this, any user's query could retrieve
    another user's medical chunks, which is an RBAC violation the moment the
    corpus holds more than one profile (guardrails doc §2: "User: ✗ Access
    other users' data").
    """
    store = get_vectorstore()
    search_filter = {"user_id": user_id} if user_id else None
    # Chroma returns a cosine *distance* (0=identical .. 2=opposite) here, not a
    # relevance score — `similarity_search_with_relevance_scores` assumes an L2
    # scaling that warns/misbehaves with normalized OpenAI embeddings, so we
    # convert the distance to a 0-1 similarity ourselves instead.
    raw_candidates = store.similarity_search_with_score(query, k=max(k * 2, 6), filter=search_filter)

    fused: list[RetrievedChunk] = []
    for doc, distance in raw_candidates:
        dense_similarity = max(0.0, 1.0 - (distance / 2.0))
        lexical = _lexical_overlap(query, doc.page_content)
        fused_score = (0.7 * dense_similarity) + (0.3 * lexical)
        fused.append(RetrievedChunk(text=doc.page_content, metadata=doc.metadata, score=fused_score))

    fused.sort(key=lambda c: c.score, reverse=True)

    # Per-document cap so top-k isn't filled with near-duplicate sections of one
    # doc (review §6). Keep at most `per_doc_cap` chunks from any single source.
    per_doc_cap = max(1, k // 2)
    per_doc_count: dict[str, int] = {}
    top: list[RetrievedChunk] = []
    for c in fused:
        src = c.metadata.get("source_file", "?")
        if per_doc_count.get(src, 0) >= per_doc_cap:
            continue
        per_doc_count[src] = per_doc_count.get(src, 0) + 1
        top.append(c)
        if len(top) >= k:
            break

    refused = not top or top[0].score < REFUSAL_MIN_SCORE
    return top, refused
