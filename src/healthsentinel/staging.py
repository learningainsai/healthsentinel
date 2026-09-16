"""Disk-persisted per-user staging queue for day-end batch analysis.

Users add category-tagged document attachments and free-text notes throughout
the day at their own pace; a single manual "Run day-end analysis" trigger (no
cron/scheduler — the user presses it whenever) consumes everything staged so
far in one graph run via `intake_agent`. The raw queue is then cleared —
only values *derived* from it (lab readings, RAG chunks) need to persist, via
`metrics_store` / the Chroma index, not the source documents themselves.

One JSON file per user under `data/staging/<user_id>.json` — this needs to
survive a page refresh/app restart (unlike the graph's in-memory checkpointer)
so staging is independent of any particular browser session.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from . import config

CATEGORIES = ["meal", "health_report", "activity", "lab", "sms", "calendar"]


def _queue_path(user_id: str) -> Path:
    return config.PATHS.staging_dir / f"{user_id}.json"


def _load(user_id: str) -> list[dict]:
    path = _queue_path(user_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(user_id: str, items: list[dict]) -> None:
    _queue_path(user_id).write_text(json.dumps(items, indent=2), encoding="utf-8")


def add_attachment(user_id: str, category: str, filename: str, content_b64: str, mime: str) -> dict:
    if category not in CATEGORIES:
        raise ValueError(f"unknown staging category: {category}")
    item = {
        "id": uuid.uuid4().hex[:8],
        "kind": "attachment",
        "category": category,
        "filename": filename,
        "content_b64": content_b64,
        "mime": mime,
        "added_at": time.time(),
    }
    items = _load(user_id)
    items.append(item)
    _save(user_id, items)
    return item


def add_note(user_id: str, text: str) -> dict:
    item = {"id": uuid.uuid4().hex[:8], "kind": "note", "text": text, "added_at": time.time()}
    items = _load(user_id)
    items.append(item)
    _save(user_id, items)
    return item


def list_items(user_id: str) -> list[dict]:
    return _load(user_id)


def remove_item(user_id: str, item_id: str) -> None:
    items = [i for i in _load(user_id) if i["id"] != item_id]
    _save(user_id, items)


def clear(user_id: str) -> int:
    """Discards the raw staged queue after a run — the derived values it
    produced (lab readings, RAG chunks) already live elsewhere; the source
    documents themselves don't need to be retained."""
    items = _load(user_id)
    _queue_path(user_id).unlink(missing_ok=True)
    return len(items)
