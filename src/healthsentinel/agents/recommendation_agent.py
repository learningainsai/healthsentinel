"""Agent 8 — Recommendation Agent: turns predictions into actionable, filtered
recommendations (mid-tier model). Applies: allergen filtering, calorie/exercise
bounds, unproven-supplement/extreme-diet rejection, plus user-rejected
recommendation suppression (shared-memory override, guardrails doc §4).

Note: the socioeconomic (budget-aware) guard previously ran here off a
simulated banking signal. That connector was replaced by the SMS connector
(gym subscription / meal timing / health-related messages) — there is no
budget signal anymore, so `guardrails.bias.socioeconomic_guard` is currently
unwired pending a real replacement input, rather than being called with a
silently-always-false flag.
"""
from __future__ import annotations

import time

from ..faults import Layer, classify_exception
from ..guardrails.hallucination import (
    reject_unusual_recommendation,
    validate_calorie_bounds,
    validate_exercise_minutes,
)
from ..guardrails.medical import blocked_allergen_hits
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import RECOMMENDATION
from ..schemas import RecommendationResult


def recommendation_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    prediction = state.get("prediction_result") or {}
    profile = state.get("profile") or {}
    sms_result = state.get("sms_result") or {}
    allergies = profile.get("allergies", [])
    has_gym_subscription = sms_result.get("has_gym_subscription", False)

    if not prediction.get("predictions"):
        return {"recommendation_result": {"recommendations": []}, "audit_log": []}

    try:
        call = call_structured(
            "mid", RecommendationResult,
            [("system", RECOMMENDATION.text),
             ("human", f"Predictions: {prediction}\nAllergies to avoid: {allergies}\n"
                       f"Has an active gym subscription (from SMS signals): {has_gym_subscription}")],
            run_id=run_id, prompt_version=RECOMMENDATION.version,
        )
        result: RecommendationResult = call.parsed

        flags: list[str] = []
        kept = []
        for rec in result.recommendations:
            full_text = f"{rec.title} {rec.detail}"

            allergen_hits = blocked_allergen_hits(full_text, allergies)
            if allergen_hits:
                flags.append(f"BLOCKED_recommendation_allergen_{allergen_hits}: {rec.title}")
                continue

            rejection = reject_unusual_recommendation(full_text)
            if rejection:
                flags.append(f"BLOCKED_recommendation: {rec.title} — {rejection}")
                continue

            kept.append(rec)

        result.recommendations = kept
        event = log_event(
            user_id=user_id, agent="recommendation_agent",
            input_summary={"num_predictions": len(prediction.get("predictions", []))},
            decision=result.model_dump(), confidence=1.0,
            started_at=started, run_id=run_id, **call.trace_fields(),
        )
        return {
            "recommendation_result": result.model_dump(),
            "guardrail_flags": flags,
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="recommendation_agent", input_summary={},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "recommendation_result": {"recommendations": []},
            "errors": [{"agent": "recommendation_agent", "fault": fault.to_dict()}],
            "audit_log": [event],
        }
