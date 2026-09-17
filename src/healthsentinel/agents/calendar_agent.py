"""Agent 6 — Calendar Agent (Google Calendar MCP, simulated) — stress indicators."""
from __future__ import annotations

from ..tools.mcp_simulated import google_calendar_stress_signals
from ._connector_helpers import run_connector

# Each user-reported note (e.g. "worked late for a demo, cutting into sleep")
# adds this many late-night events to the simulated pull, capped so a couple
# of notes can't runaway-inflate the score — the LLM only ever phrases the
# resulting number, it never invents it (review: code decides, LLM narrates).
EXTRA_LATE_NIGHT_EVENTS_PER_NOTE = 1
MAX_NOTE_DRIVEN_LATE_NIGHT_EVENTS = 3


def calendar_agent(state: dict) -> dict:
    def fetch() -> dict:
        data = google_calendar_stress_signals(state["user_id"])
        # Staged free-text/attachment notes (intake_agent) supplement the
        # simulated MCP pull — they never replace it.
        extra_notes = state.get("calendar_notes") or []
        if extra_notes:
            data["user_reported_notes"] = extra_notes
            bump = min(len(extra_notes) * EXTRA_LATE_NIGHT_EVENTS_PER_NOTE, MAX_NOTE_DRIVEN_LATE_NIGHT_EVENTS)
            data["late_night_events"] = min(10, data["late_night_events"] + bump)
            data["stress_indicator"] = min(10.0, round((data["meetings_this_week"] / 4) + (data["late_night_events"] * 1.2), 1))
        return data

    return run_connector(state=state, agent_name="calendar_agent", result_key="calendar_result",
                          source="calendar_mcp", fetch=fetch)
