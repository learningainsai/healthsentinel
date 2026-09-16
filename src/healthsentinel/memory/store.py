"""Cross-session shared memory (guardrails doc §4 — user overrides, preferences,
rejected recommendations) built on LangGraph's `Store`.

Same pattern as the Career Trajectory Optimizer's `InMemoryStore` usage: swap for
`PostgresStore`/`RedisStore` in production without touching call sites.
"""
from __future__ import annotations

import math

from langgraph.store.memory import InMemoryStore

from .. import config

NAMESPACE = "health"

# Single shared instance (also used by graph.py's compiled graph and by any
# agent that needs to read/write cross-session memory directly).
GLOBAL_STORE = InMemoryStore()


def namespace_for(user_id: str) -> tuple[str, str]:
    return (NAMESPACE, user_id)


def save_preference(store: InMemoryStore, user_id: str, key: str, value) -> None:
    """e.g. key='skip_sleep_predictions', value=True; key='allergies', value=['soy']."""
    store.put(namespace_for(user_id), f"preference:{key}", {"value": value})


def get_preference(store: InMemoryStore, user_id: str, key: str, default=None):
    item = store.get(namespace_for(user_id), f"preference:{key}")
    return item.value["value"] if item else default


def reject_recommendation(store: InMemoryStore, user_id: str, recommendation_title: str) -> None:
    key = "rejected_recommendations"
    current = get_preference(store, user_id, key, default=[])
    if recommendation_title not in current:
        current.append(recommendation_title)
    save_preference(store, user_id, key, current)


def is_rejected(store: InMemoryStore, user_id: str, recommendation_title: str) -> bool:
    return recommendation_title in get_preference(store, user_id, "rejected_recommendations", default=[])


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b + 1e-9)


def is_rejected_semantic(store: InMemoryStore, user_id: str, title: str,
                          *, threshold: float = config.REJECTED_RECOMMENDATION_SIMILARITY_THRESHOLD) -> bool:
    """Embedding-similarity version of `is_rejected` — catches a reworded
    recommendation the user already rejected (e.g. 'more leafy greens' vs 'add
    kale'). Preference/UX guard only, no medical-safety consequence either way
    (review: the similarity threshold is a deterministic decision boundary in
    code — the LLM/embedding model only proposes a similarity score)."""
    rejected = get_preference(store, user_id, "rejected_recommendations", default=[])
    if not rejected:
        return False
    if title in rejected:
        return True
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model=config.MODELS.embedding)
    vectors = embeddings.embed_documents([title] + rejected)
    new_vec, rejected_vecs = vectors[0], vectors[1:]
    return any(_cosine(new_vec, v) >= threshold for v in rejected_vecs)


def save_progress_note(store: InMemoryStore, user_id: str, note: str) -> None:
    store.put(namespace_for(user_id), "progress_note", {"value": note})


def get_progress_note(store: InMemoryStore, user_id: str) -> str | None:
    item = store.get(namespace_for(user_id), "progress_note")
    return item.value["value"] if item else None


def save_consent(store: InMemoryStore, user_id: str, consent: dict) -> None:
    store.put(namespace_for(user_id), "consent", {"value": consent})


def get_consent(store: InMemoryStore, user_id: str) -> dict:
    item = store.get(namespace_for(user_id), "consent")
    return item.value["value"] if item else {}
