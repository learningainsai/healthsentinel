"""Agent 0 — Intake Agent: turns the day-end staging queue (`staging.py`)
into the existing per-agent input fields.

Two input paths converge here:
- `staged_attachments`: the user already picked an explicit category from a
  dropdown, so routing is deterministic — no LLM needed.
- `staged_notes`: free text with no category attached, so a cheap-tier LLM
  call multi-label classifies each note (review: one note can span more
  than one category, e.g. "ran 5k and my glucose was 140") and the matching
  portions are merged into the same fields the deterministic path uses.

Every category that ends up empty after this pass is recorded in
`intake_result["missing"]` so `finalize` can tell the user what was skipped,
since a meal (and every other input) is optional for a day-end run.
"""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path

from ..faults import Layer, classify_exception
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import INTAKE_CLASSIFIER
from ..rag.vectorstore import index_user_document
from ..schemas import TextClassification


def _extract_text(filename: str, mime: str, content_b64: str) -> tuple[str | None, str | None]:
    """Returns (extracted_text, image_b64) — exactly one is non-None."""
    if mime.startswith("image/"):
        return None, content_b64
    raw = base64.b64decode(content_b64)
    if mime == "application/pdf" or Path(filename).suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        return (text or None), None
    return raw.decode("utf-8", errors="ignore").strip() or None, None


def intake_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    attachments = state.get("staged_attachments") or []
    notes = state.get("staged_notes") or []

    merged: dict = {
        "meal_text_entry": None, "meal_image_b64": None,
        "lab_report_text": None, "lab_report_image_b64": None,
        "medical_query": None,
        "activity_notes": [], "sms_notes": [], "calendar_notes": [],
    }
    indexed_health_reports = 0
    classify_cost = 0.0
    classify_tokens = 0

    def _append_text(key: str, text: str) -> None:
        if not text:
            return
        merged[key] = f"{merged[key]}\n{text}".strip() if merged[key] else text

    try:
        for att in attachments:
            category = att.get("category")
            text, image_b64 = _extract_text(att.get("filename", ""), att.get("mime", ""), att["content_b64"])
            if category == "meal":
                merged["meal_image_b64"] = merged["meal_image_b64"] or image_b64
                _append_text("meal_text_entry", text or "")
            elif category == "lab":
                merged["lab_report_image_b64"] = merged["lab_report_image_b64"] or image_b64
                _append_text("lab_report_text", text or "")
            elif category == "health_report" and text:
                indexed_health_reports += index_user_document(user_id, text, att.get("filename", "health_report"))
            elif category == "activity" and text:
                merged["activity_notes"].append(text)
            elif category == "sms" and text:
                merged["sms_notes"].append(text)
            elif category == "calendar" and text:
                merged["calendar_notes"].append(text)

        for note_text in notes:
            call = call_structured(
                "cheap", TextClassification,
                [("system", INTAKE_CLASSIFIER.text), ("human", note_text)],
                run_id=run_id, prompt_version=INTAKE_CLASSIFIER.version,
            )
            classified: TextClassification = call.parsed
            classify_cost += call.cost_usd
            classify_tokens += call.total_tokens
            _append_text("meal_text_entry", classified.meal)
            _append_text("lab_report_text", classified.lab)
            _append_text("medical_query", classified.medical)
            if classified.activity:
                merged["activity_notes"].append(classified.activity)
            if classified.sms:
                merged["sms_notes"].append(classified.sms)
            if classified.calendar:
                merged["calendar_notes"].append(classified.calendar)

        checks = {
            "meal": bool(merged["meal_text_entry"] or merged["meal_image_b64"]),
            "lab_report": bool(merged["lab_report_text"] or merged["lab_report_image_b64"]),
            "health_report": indexed_health_reports > 0,
            "medical_context": bool(merged["medical_query"]),
            "activity": bool(merged["activity_notes"]),
            "sms": bool(merged["sms_notes"]),
            "calendar": bool(merged["calendar_notes"]),
        }
        considered = [name for name, present in checks.items() if present]
        missing = [name for name, present in checks.items() if not present]

        event = log_event(
            user_id=user_id, agent="intake_agent",
            input_summary={"attachments": len(attachments), "notes": len(notes)},
            decision={"considered": considered, "missing": missing, "health_reports_indexed": indexed_health_reports},
            started_at=started, run_id=run_id,
        )
        return {
            **merged,
            "intake_result": {"considered": considered, "missing": missing},
            "run_cost_usd": classify_cost,
            "run_tokens": classify_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.AGENT)
        event = log_event(
            user_id=user_id, agent="intake_agent",
            input_summary={"attachments": len(attachments), "notes": len(notes)},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            **merged,
            "intake_result": {"considered": [], "missing": ["meal", "lab_report", "health_report", "medical_context", "activity", "sms", "calendar"]},
            "errors": [{"agent": "intake_agent", "fault": fault.to_dict()}],
            "guardrail_flags": ["intake_agent_failed_degraded_to_no_staged_input"],
            "audit_log": [event],
        }
