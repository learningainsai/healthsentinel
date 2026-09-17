"""LangGraph Ask Sentinel nodes: classify, then synthesize evidence."""
from __future__ import annotations

import time

from .. import config, metrics_store
from ..faults import Layer, classify_exception
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import ASK_ANALYSIS, ASK_CLASSIFIER
from ..schemas import AskAnalysis, AskClassification
from ..tools.mcp_simulated import google_calendar_stress_signals, iwatch_activity_log
from ..trends import classify_all


PROFILES = {
    "demo-user": {"conditions": ["prediabetes"], "allergies": ["peanuts"]},
    "healthy-baseline-user": {"conditions": [], "allergies": []},
    "hypertension-user": {"conditions": ["hypertension"], "allergies": ["shellfish"]},
    "family-history-user": {"conditions": [], "allergies": []},
}


def classify_question(state: dict) -> dict:
    started = time.time()
    prompt = state["prompt"]
    call = call_structured(
        "cheap",
        AskClassification,
        [("system", ASK_CLASSIFIER.text), ("human", f"<user_question>\n{prompt}\n</user_question>")],
        run_id=state.get("run_id"),
        prompt_version=ASK_CLASSIFIER.version,
    )
    result: AskClassification = call.parsed
    event = log_event(
        user_id=state["user_id"], agent="ask_classifier",
        input_summary={"category": result.category}, decision=result.model_dump(),
        started_at=started, run_id=state.get("run_id"), **call.trace_fields(),
    )
    return {
        "category": result.category,
        "needs_more_details": result.needs_more_details or result.category == "other",
        "classification_reason": result.reason,
        "run_cost_usd": call.cost_usd,
        "run_tokens": call.total_tokens,
        "audit_log": [event],
    }


def synthesize_answer(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    profile = state.get("profile") or PROFILES.get(user_id, {"conditions": [], "allergies": []})
    series = {
        metric: [reading.__dict__ for reading in metrics_store.get_series(user_id, metric, window_days=config.TREND_WINDOW_DAYS)]
        for metric in ("glucose_mgdl", "weight_kg", "sleep_hours")
    }
    trends = classify_all({
        metric: [metrics_store.MetricReading(**reading) for reading in readings]
        for metric, readings in series.items()
    })
    activity = iwatch_activity_log(user_id)
    calendar = google_calendar_stress_signals(user_id)
    context = (
        f"Question category: {state['category']}\n"
        f"User question: {state['prompt']}\n"
        f"Profile conditions/allergies: {profile}\n"
        f"Deterministic historic trends: {trends}\n"
        f"Recent activity/sleep connector: {activity}\n"
        f"Recent calendar stress connector: {calendar}\n"
        "No signal in this context should be treated as a diagnosis."
    )
    call = call_structured(
        "mid", AskAnalysis,
        [("system", ASK_ANALYSIS.text), ("human", context)],
        run_id=state.get("run_id"), prompt_version=ASK_ANALYSIS.version,
    )
    result: AskAnalysis = call.parsed
    event = log_event(
        user_id=user_id, agent="ask_analysis", input_summary={"category": state["category"]},
        decision=result.model_dump(), started_at=started, run_id=state.get("run_id"), **call.trace_fields(),
    )
    return {
        "analysis": result.model_dump(),
        "run_cost_usd": call.cost_usd,
        "run_tokens": call.total_tokens,
        "audit_log": [event],
    }


def ask_flow_error(state: dict, exc: Exception, agent: str) -> dict:
    fault = classify_exception(exc, layer=Layer.AGENT)
    event = log_event(
        user_id=state["user_id"], agent=agent, input_summary={}, decision=fault.message,
        status="error", started_at=time.time(), run_id=state.get("run_id"), fault=fault,
    )
    return {"errors": [{"agent": agent, "fault": fault.to_dict()}], "audit_log": [event]}
