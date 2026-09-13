"""SQLite-backed historic metrics store (glucose, weight, sleep, ...).

Chosen over the in-memory stores used elsewhere in this app (rate limiter,
`InMemoryStore`, `MemorySaver`) specifically because trend reasoning needs data
that survives a process restart across weeks/months. A single file, stdlib
`sqlite3`, real SQL for time-windowed queries — no new infra, and swapping to
Postgres later is a connection-string change, not a rewrite (same posture as
`memory/store.py`'s `InMemoryStore`).
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metric_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    recorded_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metric_readings_lookup
    ON metric_readings (user_id, metric_name, recorded_at);
"""


@dataclass(frozen=True)
class MetricReading:
    value: float
    unit: str | None
    source: str
    recorded_at: float


@contextmanager
def _connection():
    conn = sqlite3.connect(str(config.PATHS.metrics_db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connection() as conn:
        conn.executescript(_SCHEMA)


def record_metric(
    user_id: str,
    metric_name: str,
    value: float,
    *,
    unit: str | None = None,
    source: str = "pipeline",
    recorded_at: float | None = None,
) -> None:
    """Insert one timestamped reading. Callers are responsible for validating
    `value` (e.g. via `guardrails.rate_limit.is_physiologically_invalid`)
    before calling this — the store itself does not re-validate."""
    init_db()
    with _connection() as conn:
        conn.execute(
            "INSERT INTO metric_readings (user_id, metric_name, value, unit, source, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, metric_name, float(value), unit, source, recorded_at or time.time()),
        )


def get_series(user_id: str, metric_name: str, *, window_days: float | None = None) -> list[MetricReading]:
    """Returns readings for one user+metric, oldest first, optionally limited
    to a trailing window (e.g. the last `TREND_WINDOW_DAYS`)."""
    init_db()
    since = time.time() - window_days * 86400 if window_days else 0.0
    with _connection() as conn:
        rows = conn.execute(
            "SELECT value, unit, source, recorded_at FROM metric_readings "
            "WHERE user_id = ? AND metric_name = ? AND recorded_at >= ? "
            "ORDER BY recorded_at ASC",
            (user_id, metric_name, since),
        ).fetchall()
    return [MetricReading(value=r[0], unit=r[1], source=r[2], recorded_at=r[3]) for r in rows]


def delete_user_metrics(user_id: str) -> int:
    """Right-to-be-forgotten path, mirrors `rag.vectorstore.delete_user_documents`."""
    init_db()
    with _connection() as conn:
        cur = conn.execute("DELETE FROM metric_readings WHERE user_id = ?", (user_id,))
        return cur.rowcount
