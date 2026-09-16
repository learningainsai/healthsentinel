"""Agent 4 — Activity Agent (iWatch MCP, simulated)."""
from __future__ import annotations

from .. import metrics_store
from ..tools.mcp_simulated import iwatch_activity_log
from ._connector_helpers import run_connector


def activity_agent(state: dict) -> dict:
    user_id = state["user_id"]

    def fetch() -> dict:
        data = iwatch_activity_log(user_id)
        if data.get("avg_sleep_hours") is not None:
            # Persisted so trend_agent can reason over sleep history, not just this turn's value.
            metrics_store.record_metric(user_id, "sleep_hours", data["avg_sleep_hours"], unit="hours", source="iwatch_mcp")
        # Staged free-text/attachment notes (intake_agent) supplement the
        # simulated MCP pull — they never replace it.
        extra_notes = state.get("activity_notes") or []
        if extra_notes:
            data["user_reported_notes"] = extra_notes
        return data

    return run_connector(state=state, agent_name="activity_agent", result_key="activity_result",
                          source="iwatch_mcp", fetch=fetch)
