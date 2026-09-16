"""Advisory-only cross-metric insight agent.

Runs after the deterministic verifier/critic and is explicitly NOT part of the
guardrail chain: its output (`insight_notes`) is surfaced in the final report
as clearly-labeled AI observations and can never change severity, guardrail
flags, or trigger nutritionist review. It is given the same historic trend
verdicts prediction_agent uses (already computed deterministically) and is
told to phrase/correlate, never recompute them (same pattern as PREDICTION).
"""
from __future__ import annotations

import time

from ..faults import Layer, classify_exception
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import INSIGHT
from ..schemas import InsightResult


def insight_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")

    predictions = (state.get("prediction_result") or {}).get("predictions", [])
    if not predictions:
        return {"insight_notes": [], "audit_log": []}

    context_text = (
        f"Historic trends (deterministic, ground truth — do not recompute): {state.get('trend_context')}\n"
        f"Nutrition: {state.get('nutrition_result')}\n"
        f"Activity: {state.get('activity_result')}\n"
        f"Calendar/stress: {state.get('calendar_result')}\n"
        f"SMS-confirmed signals: {state.get('sms_confirmed')}"
    )

    try:
        call = call_structured(
            "mid", InsightResult,
            [("system", INSIGHT.text), ("human", context_text)],
            run_id=run_id, prompt_version=INSIGHT.version,
        )
        result: InsightResult = call.parsed
        notes = [n.observation for n in result.notes]

        event = log_event(
            user_id=user_id, agent="insight_agent", input_summary={"context": "cross-metric"},
            decision={"notes": notes}, started_at=started, run_id=run_id, **call.trace_fields(),
        )
        return {
            "insight_notes": notes,
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="insight_agent", input_summary={},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "insight_notes": [],
            "errors": [{"agent": "insight_agent", "fault": fault.to_dict()}],
            "audit_log": [event],
        }
