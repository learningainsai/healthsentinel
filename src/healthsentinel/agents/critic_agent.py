"""Critic Agent — reviews the full run against the guardrails checklist before
the final report is released (mirrors the Career Trajectory Optimizer's
critic subagent pattern, applied to the guardrails-doc quick-reference
checklist instead of a career-roadmap methodology)."""
from __future__ import annotations

import time

from ..faults import Layer, classify_exception
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import CRITIC
from ..schemas import CriticReview


def critic_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    payload = {
        "prediction_result": state.get("prediction_result"),
        "recommendation_result": state.get("recommendation_result"),
        "medical_context": state.get("medical_context"),
        "guardrail_flags": state.get("guardrail_flags", []),
        "profile": state.get("profile"),
    }
    try:
        call = call_structured(
            "reasoning", CriticReview,
            [("system", CRITIC.text), ("human", str(payload))],
            run_id=run_id, prompt_version=CRITIC.version,
        )
        result: CriticReview = call.parsed
        event = log_event(
            user_id=user_id, agent="critic_agent", input_summary={"reviewed": "final_run"},
            decision=result.model_dump(), confidence=result.guardrail_score,
            started_at=started, run_id=run_id, **call.trace_fields(),
        )
        return {
            "critic_review": result.model_dump(),
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="critic_agent", input_summary={"reviewed": "final_run"},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "critic_review": {"passed": False, "issues": [f"critic_failed: {fault.message}"], "guardrail_score": 0.0,
                               "summary": "Critic review failed — treat as unreviewed (advisory only)."},
            "errors": [{"agent": "critic_agent", "fault": fault.to_dict()}],
            "audit_log": [event],
        }
