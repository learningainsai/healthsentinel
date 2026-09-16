"""Shared boilerplate for simulated-MCP connector agents (activity, calendar,
sms). Each connector keeps its own graph node, audit trail, and consent
toggle (review: merging them would lose per-connector fault isolation and the
ability to swap one to a real integration later) — this only removes the
duplicated try/except/log_event wiring each one hand-rolled independently.
"""
from __future__ import annotations

import time
from typing import Callable

from ..faults import Layer, classify_exception
from ..logging_utils import log_event


def run_connector(
    *,
    state: dict,
    agent_name: str,
    result_key: str,
    source: str,
    fetch: Callable[[], dict],
    layer: Layer = Layer.TOOL,
    skip: bool = False,
    input_summary: dict | None = None,
) -> dict:
    """Runs `fetch()`, logs a structured audit event, and shapes the standard
    `{<result_key>: ..., audit_log: [...]}` / `{..., errors: [...]}` return.
    `skip=True` short-circuits with an empty result and no audit event,
    matching each agent's existing graceful-skip behavior (e.g. sms_agent
    when nothing was confirmed this turn)."""
    if skip:
        return {result_key: {}, "audit_log": []}

    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    summary = input_summary if input_summary is not None else {"source": source}
    try:
        data = fetch()
        event = log_event(
            user_id=user_id, agent=agent_name, input_summary=summary,
            decision=data, confidence=1.0, started_at=started, run_id=run_id,
        )
        return {result_key: data, "audit_log": [event]}
    except Exception as e:
        fault = classify_exception(e, layer=layer)
        event = log_event(
            user_id=user_id, agent=agent_name, input_summary=summary,
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            result_key: {},
            "errors": [{"agent": agent_name, "fault": fault.to_dict()}],
            "audit_log": [event],
        }
