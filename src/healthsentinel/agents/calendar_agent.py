"""Agent 6 — Calendar Agent (Google Calendar MCP, simulated) — stress indicators."""
from __future__ import annotations

from ..tools.mcp_simulated import google_calendar_stress_signals
from ._connector_helpers import run_connector


def calendar_agent(state: dict) -> dict:
    def fetch() -> dict:
        data = google_calendar_stress_signals(state["user_id"])
        # Staged free-text/attachment notes (intake_agent) supplement the
        # simulated MCP pull — they never replace it.
        extra_notes = state.get("calendar_notes") or []
        if extra_notes:
            data["user_reported_notes"] = extra_notes
        return data

    return run_connector(state=state, agent_name="calendar_agent", result_key="calendar_result",
                          source="calendar_mcp", fetch=fetch)
