"""Cross-session shared memory (guardrails doc §4 — user overrides, preferences,
rejected recommendations) built on LangGraph's `Store`.

Same pattern as the Career Trajectory Optimizer's `InMemoryStore` usage: swap for
`PostgresStore`/`RedisStore` in production without touching call sites.
"""
from __future__ import annotations

from langgraph.store.memory import InMemoryStore

NAMESPACE = "health"


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
