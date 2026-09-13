"""Agent 1 — Vision Agent: meal-photo food recognition (cheap/fast model tier).

Guardrails applied here: hallucination floor (confidence < 0.50 -> require
manual confirmation, do not proceed with analysis) and graceful degradation
(image unreadable -> prompt for manual entry, never blocks the whole run).
"""
from __future__ import annotations

import time

from langchain_core.messages import HumanMessage

from .. import config
from ..faults import Layer, classify_exception
from ..guardrails.hallucination import vision_requires_manual_confirmation
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import VISION
from ..schemas import VisionResult


def vision_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    image_b64 = state.get("meal_image_b64")

    if not image_b64:
        return {"vision_result": {}, "audit_log": []}  # no image this turn — skip gracefully

    try:
        message = HumanMessage(content=[
            {"type": "text", "text": "Identify the food items and estimate calories in this meal photo."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ])
        call = call_structured(
            "cheap", VisionResult, [("system", VISION.text), message],
            run_id=run_id, prompt_version=VISION.version,
        )
        result: VisionResult = call.parsed
        flags = []
        if vision_requires_manual_confirmation(result.confidence):
            flags.append("vision_confidence_below_floor_manual_confirmation_required")
        if result.confidence < config.VISION_MIN_ACCURACY:
            flags.append("vision_confidence_below_85pct_threshold")

        event = log_event(
            user_id=user_id, agent="vision_agent",
            input_summary={"has_image": True},
            decision=result.model_dump(), confidence=result.confidence,
            started_at=started, run_id=run_id, **call.trace_fields(),
        )
        return {
            "vision_result": result.model_dump(),
            "guardrail_flags": flags,
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="vision_agent", input_summary={"has_image": True},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "vision_result": {},
            "errors": [{"agent": "vision_agent", "fault": fault.to_dict()}],
            "guardrail_flags": ["vision_agent_failed_degraded_to_manual_entry"],
            "audit_log": [event],
        }
