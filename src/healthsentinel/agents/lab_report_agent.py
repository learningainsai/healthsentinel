"""Agent — Lab Report extraction: turns an uploaded lab report (text/PDF text
or a photo) into validated metric readings, persisted to the historic metrics
store for trend reasoning.

The LLM only proposes candidate readings via structured output; every reading
is then checked against a fixed metric-name allowlist and physiological
bounds before it is ever written to the database (review §2 — a raw model
number never reaches a persistence boundary unvalidated).
"""
from __future__ import annotations

import time

from langchain_core.messages import HumanMessage

from .. import config, metrics_store
from ..faults import Layer, classify_exception
from ..guardrails.rate_limit import is_physiologically_invalid
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import LAB_EXTRACTION
from ..schemas import LabExtraction


def lab_report_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    report_text = state.get("lab_report_text")
    report_image_b64 = state.get("lab_report_image_b64")

    if not report_text and not report_image_b64:
        return {"lab_report_result": {}, "audit_log": []}  # nothing uploaded this turn

    try:
        if report_image_b64:
            message = HumanMessage(content=[
                {"type": "text", "text": "Extract lab parameters from this lab report photo."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{report_image_b64}"}},
            ])
            messages = [("system", LAB_EXTRACTION.text), message]
            tier = "cheap"
        else:
            messages = [("system", LAB_EXTRACTION.text), ("human", f"Lab report content:\n\n{report_text}")]
            tier = "mid"

        call = call_structured(
            tier, LabExtraction, messages, run_id=run_id, prompt_version=LAB_EXTRACTION.version,
        )
        result: LabExtraction = call.parsed

        accepted: list[dict] = []
        rejected: list[str] = []
        for reading in result.readings:
            metric_name = reading.metric_name.strip().lower()
            if metric_name not in config.ALLOWED_LAB_METRICS:
                rejected.append(f"{reading.metric_name}: not in allowed metric list")
                continue
            invalid_reason = is_physiologically_invalid(metric_name, reading.value)
            if invalid_reason:
                rejected.append(invalid_reason)
                continue
            metrics_store.record_metric(
                user_id, metric_name, reading.value, unit=reading.unit, source="lab_report_upload",
            )
            accepted.append({"metric_name": metric_name, "value": reading.value, "unit": reading.unit})

        event = log_event(
            user_id=user_id, agent="lab_report_agent",
            input_summary={"has_image": bool(report_image_b64), "has_text": bool(report_text)},
            decision={"accepted": accepted, "rejected": rejected},
            confidence=None, started_at=started, run_id=run_id, **call.trace_fields(),
        )
        flags = [f"lab_reading_rejected: {r}" for r in rejected]
        return {
            "lab_report_result": {"accepted": accepted, "rejected": rejected},
            "guardrail_flags": flags,
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="lab_report_agent", input_summary={"has_image": bool(report_image_b64)},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "lab_report_result": {},
            "errors": [{"agent": "lab_report_agent", "fault": fault.to_dict()}],
            "guardrail_flags": ["lab_report_agent_failed_no_readings_persisted"],
            "audit_log": [event],
        }
