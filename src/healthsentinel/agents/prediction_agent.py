"""Agent 7 — Prediction Engine: turns nutrition + activity + medical + calendar
context into SAFE-category-only predictions and a 5-axis-style risk dashboard.

Runs on the reasoning-tier model (highest stakes, lowest volume — guardrails
doc cost-ceiling rationale). Applies: blocked-category hard stop, confidence
cap (never >0.92), and severity gating from raw signals.
"""
from __future__ import annotations

import time

from ..guardrails.hallucination import cap_confidence
from ..guardrails.medical import (
    adjust_for_medical_history,
    is_blocked_category,
    is_safe_category,
    severity_from_signals,
)
from ..faults import classify_exception, Layer
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import PREDICTION
from ..schemas import PredictionResult


def prediction_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")

    nutrition = state.get("nutrition_result") or {}
    activity = state.get("activity_result") or {}
    medical = state.get("medical_context") or {}
    calendar = state.get("calendar_result") or {}
    profile = state.get("profile") or {}
    trend_context = state.get("trend_context") or {}

    context_text = (
        f"Nutrition: {nutrition}\nActivity: {activity}\nMedical context: {medical}\n"
        f"Calendar/stress: {calendar}\nKnown conditions: {profile.get('conditions', [])}\n"
        f"Historic trends (already computed deterministically — phrase, don't recompute): {trend_context}"
    )

    try:
        call = call_structured(
            "reasoning", PredictionResult,
            [("system", PREDICTION.text), ("human", context_text)],
            run_id=run_id, prompt_version=PREDICTION.version,
        )
        result: PredictionResult = call.parsed

        flags: list[str] = []
        kept_predictions = []
        for p in result.predictions:
            # Allowlist: keep ONLY safe categories; anything outside the SAFE set
            # (including unknown categories in neither set) is suppressed (review §2).
            if not is_safe_category(p.category):
                reason = "blocked" if is_blocked_category(p.category) else "not_in_safe_allowlist"
                flags.append(f"BLOCKED_prediction_category_{p.category}_{reason}")
                continue
            capped, note = cap_confidence(p.confidence)
            p.confidence = capped
            if note:
                flags.append(f"confidence_capped_for_{p.category}: {note}")
            kept_predictions.append(p)
        result.predictions = kept_predictions

        # Historic trend verdicts feed severity deterministically — a sustained
        # glucose/sleep trend or a rapid weight change escalates urgency the same
        # way a single-turn signal already does (review: history informs code,
        # not just the LLM's phrasing).
        glucose_trend = trend_context.get("glucose_mgdl") or {}
        weight_trend = trend_context.get("weight_kg") or {}
        sleep_trend = trend_context.get("sleep_hours") or {}

        effective_sleep_hours = activity.get("avg_sleep_hours")
        if sleep_trend.get("sample_count", 0) >= 3:
            effective_sleep_hours = sleep_trend.get("mean_value", effective_sleep_hours)

        extreme_weight_loss = bool(
            weight_trend.get("flag_for_doctor")
            and weight_trend.get("latest_value") is not None
            and weight_trend.get("baseline_value") is not None
            and weight_trend["latest_value"] < weight_trend["baseline_value"]
        )

        adjustments = adjust_for_medical_history(profile.get("conditions", []))
        severity = severity_from_signals(
            glucose_mgdl=glucose_trend.get("latest_value"),  # from lab-report history, if any
            sleep_hours=effective_sleep_hours,
            magnesium_deficient=nutrition.get("magnesium_mg", 999) < 310,
            stress_score=calendar.get("stress_indicator"),
            extreme_weight_loss=extreme_weight_loss,
        )
        if glucose_trend.get("flag_for_doctor") and severity.severity in {"LOW", "MEDIUM"}:
            severity.severity = "HIGH"
            severity.reasons.append(f"glucose trend: {glucose_trend.get('evidence')}")
        if sleep_trend.get("flag_for_doctor") and severity.severity == "LOW":
            severity.severity = "MEDIUM"
            severity.reasons.append(f"sleep trend: {sleep_trend.get('evidence')}")
        if adjustments["doctor_appt_urgency_bump"] and severity.severity in {"LOW", "MEDIUM"}:
            severity.severity = "HIGH"
            severity.reasons.append("prediabetes history bumps doctor-appointment urgency")

        overall_conf = max((p.confidence for p in result.predictions), default=0.5)
        event = log_event(
            user_id=user_id, agent="prediction_agent", input_summary={"context": "nutrition+activity+medical+calendar"},
            decision=result.model_dump(), confidence=overall_conf, severity=severity.severity,
            started_at=started, run_id=run_id, **call.trace_fields(),
        )
        return {
            "prediction_result": result.model_dump(),
            "severity": severity.severity,
            "guardrail_flags": flags + [f"severity_{severity.severity}: {r}" for r in severity.reasons],
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="prediction_agent", input_summary={"context": "nutrition+activity+medical+calendar"},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "prediction_result": {},
            "severity": "LOW",
            "errors": [{"agent": "prediction_agent", "fault": fault.to_dict()}],
            "guardrail_flags": ["prediction_engine_failed_no_predictions_shown_support_alerted"],
            "audit_log": [event],
        }
