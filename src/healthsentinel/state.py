"""LangGraph state schema for the Health Sentinel pipeline."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}


class HealthState(TypedDict, total=False):
    # --- identity & consent -------------------------------------------------
    user_id: str
    run_id: str  # graph thread id, threaded into every audit event for replay
    consent: dict  # tier1_core, tier2_mcp, tier3_analytics, tier4_notifications
    profile: dict  # age, conditions, allergies, diet, is_new_user

    # --- raw inputs ----------------------------------------------------------
    meal_image_b64: str | None
    meal_text_entry: str | None
    medical_query: str | None
    lab_report_text: str | None       # extracted text from an uploaded PDF/txt/md lab report
    lab_report_image_b64: str | None  # uploaded lab report photo, if not text-extractable

    # --- per-agent outputs -----------------------------------------------------
    vision_result: dict
    nutrition_result: dict
    medical_context: dict
    activity_result: dict
    sms_confirmed: dict  # user-reviewed subset of parsed SMS signals (checkboxes in the UI)
    sms_result: dict
    calendar_result: dict
    lab_report_result: dict
    trend_context: dict  # deterministic glucose/weight/sleep trend verdicts (see trends.py)
    prediction_result: dict
    recommendation_result: dict
    critic_review: dict
    verifier_passed: bool
    verifier_issues: Annotated[list[str], operator.add]

    # --- guardrail state -------------------------------------------------------
    guardrail_flags: Annotated[list[str], operator.add]
    severity: str
    requires_human_review: bool
    human_review_reasons: Annotated[list[str], operator.add]
    human_decision: str | None  # approve | modify | reject
    review_stage: str  # "pre_recommendation" | "post_verifier" -- which gate raised the HITL interrupt
    blocked: bool
    block_reason: str | None

    # --- traceability ------------------------------------------------------------
    audit_log: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
    run_cost_usd: Annotated[float, operator.add]
    run_tokens: Annotated[int, operator.add]
    run_status: str  # "success" | "degraded"
    recovered_faults: int

    # --- final -----------------------------------------------------------------------
    final_report: str
