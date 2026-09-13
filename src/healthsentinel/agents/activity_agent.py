"""Agent 4 — Activity Agent (iWatch MCP, simulated)."""
from __future__ import annotations

import time

from .. import metrics_store
from ..faults import Layer, classify_exception
from ..logging_utils import log_event
from ..tools.mcp_simulated import iwatch_activity_log


def activity_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    try:
        data = iwatch_activity_log(user_id)
        if data.get("avg_sleep_hours") is not None:
            # Persisted so trend_agent can reason over sleep history, not just this turn's value.
            metrics_store.record_metric(user_id, "sleep_hours", data["avg_sleep_hours"], unit="hours", source="iwatch_mcp")
        event = log_event(
            user_id=user_id, agent="activity_agent", input_summary={"source": "iwatch_mcp"},
            decision=data, confidence=1.0, started_at=started, run_id=run_id,
        )
        return {"activity_result": data, "audit_log": [event]}
    except Exception as e:
        fault = classify_exception(e, layer=Layer.TOOL)
        event = log_event(
            user_id=user_id, agent="activity_agent", input_summary={"source": "iwatch_mcp"},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "activity_result": {},
            "errors": [{"agent": "activity_agent", "fault": fault.to_dict()}],
            "audit_log": [event],
        }
