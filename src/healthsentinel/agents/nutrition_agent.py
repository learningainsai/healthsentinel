"""Agent 2 — Nutrition Agent: maps a described meal to canonical food keys via
the LLM, then computes macro/micronutrient totals *deterministically* from a
fixed nutrition table (review §1 — arithmetic is code, not an LLM guess).

Guardrails applied here: physiological-validity rejection and 3-sigma anomaly
detection on the computed calorie total (review §7 — previously dead code).
"""
from __future__ import annotations

import time

from ..faults import Layer, classify_exception
from ..guardrails.rate_limit import is_anomalous, is_physiologically_invalid
from ..llm import call_structured
from ..logging_utils import log_event
from ..nutrition_db import ALLOWED_FOOD_KEYS, compute_nutrition
from ..prompts import NUTRITION_MAPPING
from ..schemas import FoodMapping


def nutrition_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    food_desc = ""
    vision_result = state.get("vision_result") or {}
    if vision_result.get("food_items"):
        food_desc = ", ".join(vision_result["food_items"])
    elif state.get("meal_text_entry"):
        food_desc = state["meal_text_entry"]

    if not food_desc:
        return {"nutrition_result": {}, "audit_log": []}

    try:
        human = (
            f"Meal: {food_desc}\n\n"
            f"Allowed canonical keys: {', '.join(ALLOWED_FOOD_KEYS)}\n"
            "Return each food as a canonical key from that list plus a servings multiplier."
        )
        call = call_structured(
            "mid", FoodMapping,
            [("system", NUTRITION_MAPPING.text), ("human", human)],
            run_id=run_id, prompt_version=NUTRITION_MAPPING.version,
        )
        mapping: FoodMapping = call.parsed

        mapped_items = [(m.canonical_key, m.servings) for m in mapping.items]
        result, flags, coverage = compute_nutrition(mapped_items)

        total_calories = result["total_calories"]
        invalid = is_physiologically_invalid("calories", total_calories)
        if invalid:
            flags.append(invalid)
        anomalous, anomaly_note = is_anomalous(user_id, "calories", float(total_calories))
        if anomalous:
            flags.append(anomaly_note)
        result["flags"] = flags

        event = log_event(
            user_id=user_id, agent="nutrition_agent",
            input_summary={"food_desc": food_desc, "mapped": mapped_items},
            decision=result, confidence=coverage / 100,
            started_at=started, run_id=run_id, **call.trace_fields(),
        )
        return {
            "nutrition_result": result,
            "guardrail_flags": flags,
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="nutrition_agent", input_summary={"food_desc": food_desc},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "nutrition_result": {},
            "errors": [{"agent": "nutrition_agent", "fault": fault.to_dict()}],
            "guardrail_flags": ["nutrition_agent_failed_using_cached_or_partial_data"],
            "audit_log": [event],
        }
