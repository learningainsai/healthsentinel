"""Agent 5 — SMS Agent: ingests user-confirmed SMS-derived signals (meal-timing
patterns, gym subscription, health-related messages). Parsing + keyword
matching already happened deterministically in `sms_parser.py`; the user
already reviewed and unchecked anything not applicable in the UI before this
node ever runs — this node only logs and shapes the confirmed subset for
downstream agents (the human confirmation step is the validation boundary
here, since there is no LLM call to schema-validate).
"""
from __future__ import annotations

from ..faults import Layer
from ._connector_helpers import run_connector


def sms_agent(state: dict) -> dict:
    confirmed = state.get("sms_confirmed") or {}
    extra_notes = state.get("sms_notes") or []
    skip = not any(confirmed.get(k) for k in ("meal_timing", "gym_subscription", "health_related")) and not extra_notes

    def fetch() -> dict:
        meal_timing = confirmed.get("meal_timing", [])
        gym_subscription = confirmed.get("gym_subscription", [])
        health_related = confirmed.get("health_related", [])
        result = {
            "meal_timing": meal_timing,
            "gym_subscription": gym_subscription,
            "health_related": health_related,
            "has_gym_subscription": bool(gym_subscription),
            "meal_buckets_observed": sorted({m["meal_bucket"] for m in meal_timing}),
        }
        # Staged free-text/attachment notes (intake_agent) supplement the
        # simulated SMS inbox — they never replace it.
        if extra_notes:
            result["user_reported_notes"] = extra_notes
        return result

    return run_connector(
        state=state, agent_name="sms_agent", result_key="sms_result", source="sms_confirmed_ui",
        layer=Layer.AGENT, fetch=fetch, skip=skip,
        input_summary={"confirmed_counts": {k: len(v) for k, v in confirmed.items()}},
    )
