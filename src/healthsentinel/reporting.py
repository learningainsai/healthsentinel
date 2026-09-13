"""Traceability reporting — renders the audit trail as a markdown report under
`docs/` and prints it to the console, instead of a live table inside the
Streamlit UI. Keeps per-run trace data (hashed ids, redacted inputs, decisions,
cost/tokens) out of the shared UI surface while still making it inspectable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import config
from .logging_utils import read_recent_events

REPORT_PATH = config.PATHS.project_root / "docs" / "audit_trace_report.md"

_COLUMNS = ("timestamp", "run_id", "agent", "status", "confidence", "severity", "latency_ms", "cost_usd")


def _format_table(events: list[dict]) -> str:
    header = "| " + " | ".join(_COLUMNS) + " |"
    sep = "|" + "|".join(["---"] * len(_COLUMNS)) + "|"
    rows = [header, sep]
    for e in events:
        rows.append("| " + " | ".join(str(e.get(c, "")) for c in _COLUMNS) + " |")
    return "\n".join(rows)


def generate_report_markdown(limit: int = 200) -> str:
    events = list(reversed(read_recent_events(limit=limit)))
    generated_at = datetime.now(timezone.utc).isoformat()
    body = _format_table(events) if events else "_No audit events yet — run an analysis first._"
    return (
        "# Health Sentinel — Traceability Report\n\n"
        f"_Generated {generated_at} — most recent {len(events)} audit event(s), newest first._\n\n"
        f"{body}\n"
    )


def write_report(limit: int = 200) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(generate_report_markdown(limit=limit), encoding="utf-8")
    return REPORT_PATH


def print_report(limit: int = 200) -> None:
    print(generate_report_markdown(limit=limit))
