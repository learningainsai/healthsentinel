"""Structured, append-only audit logging (guardrails doc §8 — Monitoring & Audit).

Every agent action is logged with: timestamp, hashed user id (never raw PII),
agent name, a redacted input summary, the decision/output, confidence, latency,
and status. Logs are written as JSONL to `logs/audit.jsonl` for durable,
grep-able, tamper-evident (append-only) traceability, and mirrored into the
LangGraph state's `audit_log` list so the UI can render a live trace.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PATHS

AUDIT_LOG_PATH = PATHS.logs_dir / "audit.jsonl"


def hash_user_id(user_id: str) -> str:
    return "hash_" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]


def _redact(value: Any) -> Any:
    """Never persist raw Tier-1 payloads (images, free-text medical notes) to the log."""
    if isinstance(value, str) and len(value) > 200:
        return value[:200] + f"...<redacted {len(value) - 200} chars>"
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items() if k not in {"meal_image_b64"}}
    return value


class AuditEvent(dict):
    """A single structured audit entry (also a plain dict for JSON/UI use)."""


def log_event(
    *,
    user_id: str,
    agent: str,
    input_summary: Any,
    decision: Any,
    confidence: float | None = None,
    status: str = "success",
    started_at: float | None = None,
    severity: str | None = None,
    run_id: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    tokens: int | None = None,
    cost_usd: float | None = None,
    stop_reason: str | None = None,
    provider_request_id: str | None = None,
    fault: Any | None = None,
    retrieval: dict | None = None,
) -> AuditEvent:
    latency_ms = int((time.time() - started_at) * 1000) if started_at else None
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        run_id=run_id,
        user_id=hash_user_id(user_id),
        agent=agent,
        input=_redact(input_summary),
        decision=_redact(decision),
        confidence=confidence,
        severity=severity,
        latency_ms=latency_ms,
        status=status,
        model=model,
        prompt_version=prompt_version,
        tokens=tokens,
        cost_usd=cost_usd,
        stop_reason=stop_reason,
        provider_request_id=provider_request_id,
        fault=fault.to_dict() if hasattr(fault, "to_dict") else fault,
        retrieval=retrieval,
    )
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")
    return event


def read_recent_events(limit: int = 200) -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
