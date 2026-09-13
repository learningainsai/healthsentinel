"""Agent 6 — Calendar Agent (Google Calendar MCP, simulated) — stress indicators."""
from __future__ import annotations

import time

from ..faults import Layer, classify_exception
from ..logging_utils import log_event
from ..tools.mcp_simulated import google_calendar_stress_signals


def calendar_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    try:
        data = google_calendar_stress_signals(user_id)
        event = log_event(
            user_id=user_id, agent="calendar_agent", input_summary={"source": "calendar_mcp"},
            decision=data, confidence=1.0, started_at=started, run_id=run_id,
        )
        return {"calendar_result": data, "audit_log": [event]}
    except Exception as e:
        fault = classify_exception(e, layer=Layer.TOOL)
        event = log_event(
            user_id=user_id, agent="calendar_agent", input_summary={"source": "calendar_mcp"},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "calendar_result": {},
            "errors": [{"agent": "calendar_agent", "fault": fault.to_dict()}],
            "audit_log": [event],
        }
