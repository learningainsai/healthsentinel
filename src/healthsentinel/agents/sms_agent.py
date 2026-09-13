"""Agent 5 — SMS Agent: ingests user-confirmed SMS-derived signals (meal-timing
patterns, gym subscription, health-related messages). Parsing + keyword
matching already happened deterministically in `sms_parser.py`; the user
already reviewed and unchecked anything not applicable in the UI before this
node ever runs — this node only logs and shapes the confirmed subset for
downstream agents (the human confirmation step is the validation boundary
here, since there is no LLM call to schema-validate).
"""
from __future__ import annotations

import time

from ..faults import Layer, classify_exception
from ..logging_utils import log_event


def sms_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    confirmed = state.get("sms_confirmed") or {}

    if not any(confirmed.get(k) for k in ("meal_timing", "gym_subscription", "health_related")):
        return {"sms_result": {}, "audit_log": []}

    try:
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
        event = log_event(
            user_id=user_id, agent="sms_agent",
            input_summary={"confirmed_counts": {k: len(v) for k, v in confirmed.items()}},
            decision=result, confidence=1.0, started_at=started, run_id=run_id,
        )
        return {"sms_result": result, "audit_log": [event]}
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="sms_agent", input_summary={},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "sms_result": {},
            "errors": [{"agent": "sms_agent", "fault": fault.to_dict()}],
            "audit_log": [event],
        }
