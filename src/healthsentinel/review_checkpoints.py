"""Mandatory human-in-the-loop review/edit checkpoints for LLM agent outputs.

Every LLM-generated stage output (vision, nutrition mapping, medical RAG
context, lab extraction, prediction, recommendation, critic, insight) is
shown to the user as an editable, human-readable summary before it is used by
the next stage or written into the final report/audit trail. This is
deliberately a *mandatory* pause (not opt-in) for every stage that actually
produced output.

Any edit is re-validated with the deterministic prompt-injection scanner
(guardrails/prompt_injection.py) before it is accepted -- if the scanner
flags the edited text, the checkpoint re-prompts with the issue instead of
silently accepting or silently dropping the edit.
"""
from __future__ import annotations

import time

from langgraph.types import interrupt

from .guardrails.prompt_injection import assert_safe_for_llm
from .logging_utils import log_event


def human_edit_checkpoint(state: dict, *, stage: str, label: str, content: str) -> dict:
    """Pause and let the user review/edit `content`. Loops (re-interrupts)
    until the edited text passes the prompt-injection scan. Returns a graph
    state update with `{stage}_reviewed_text` set to the accepted text, or
    `{}` if there was nothing to review this run."""
    if not content or not content.strip():
        return {}

    user_id = state.get("user_id")
    run_id = state.get("run_id")
    current_text = content
    error: str | None = None
    attempts = 0
    injection_attempts = 0

    while True:
        attempts += 1
        response = interrupt({
            "kind": "human_edit",
            "stage": stage,
            "label": label,
            "content": current_text,
            "error": error,
        })
        edited_text = response.get("edited_text", current_text) if isinstance(response, dict) else str(response)

        is_safe, issues, clean_text = assert_safe_for_llm(edited_text)
        if is_safe:
            event = log_event(
                user_id=user_id, agent=f"human_review::{stage}",
                input_summary={"stage": stage, "attempts": attempts},
                decision={"edited": clean_text != content},
                started_at=time.time(), run_id=run_id,
            )
            flags = [f"human_edit_blocked_injection_attempt_at_{stage}"] * injection_attempts
            return {f"{stage}_reviewed_text": clean_text, "audit_log": [event], "guardrail_flags": flags}

        injection_attempts += 1
        current_text = edited_text
        error = "; ".join(issues)


def summarize_vision(result: dict) -> str:
    if not result:
        return ""
    items = ", ".join(result.get("food_items", []))
    calories = result.get("estimated_calories")
    confidence = result.get("confidence")
    parts = [f"Identified meal: {items or 'no food items recognized'}"]
    if calories is not None:
        parts.append(f"~{calories} kcal")
    if confidence is not None:
        parts.append(f"confidence {confidence:.0%}")
    return " — ".join(parts)


def summarize_nutrition(result: dict) -> str:
    if not result:
        return ""
    lines = [
        f"Calories: {result.get('total_calories', '?')} kcal",
        f"Protein: {result.get('protein_g', '?')}g",
        f"Carbs: {result.get('carbs_g', '?')}g",
        f"Fat: {result.get('fat_g', '?')}g",
        f"Fiber: {result.get('fiber_g', '?')}g",
        f"Magnesium: {result.get('magnesium_mg', '?')}mg",
    ]
    text = "Meal nutrition summary — " + ", ".join(lines)
    if result.get("flags"):
        text += f"\nFlags: {'; '.join(result['flags'])}"
    return text


def summarize_medical(context: dict) -> str:
    if not context:
        return ""
    if context.get("refused"):
        return f"Medical context: {context.get('summary', 'insufficient evidence — no answer given')}"
    lines = [context.get("summary", "")]
    if context.get("citations"):
        lines.append(f"Citations: {', '.join(context['citations'])}")
    return "\n".join(line for line in lines if line)


def summarize_lab(result: dict) -> str:
    if not result:
        return ""
    lines = ["Lab report summary:"]
    for reading in result.get("accepted", []):
        lines.append(f"- {reading['metric_name']}: {reading['value']} {reading.get('unit', '')}".rstrip())
    if result.get("rejected"):
        lines.append("Rejected readings: " + "; ".join(result["rejected"]))
    lines.append("\nDoctor's final verdict (add your own note if reviewing this report): ")
    return "\n".join(lines)


def summarize_prediction(result: dict) -> str:
    if not result or not result.get("predictions"):
        return ""
    lines = []
    for p in result["predictions"]:
        lines.append(
            f"- {p['category']} ({p['confidence']:.0%} confidence, severity {p['severity']}): "
            f"{p['statement']} — why: {p['explanation']}"
        )
    return "Predictions:\n" + "\n".join(lines)


def summarize_recommendation(result: dict) -> str:
    if not result or not result.get("recommendations"):
        return ""
    lines = [f"- {r['title']} — {r['detail']} (data: {r['data_support']})" for r in result["recommendations"]]
    return "Recommendations:\n" + "\n".join(lines)


def summarize_critic(result: dict) -> str:
    if not result:
        return ""
    badge = "PASSED" if result.get("passed") else "ISSUES FOUND"
    lines = [f"Critic review: {badge} (guardrail score {result.get('guardrail_score', 0):.0%})"]
    if result.get("summary"):
        lines.append(result["summary"])
    if result.get("issues"):
        lines.append("Issues: " + "; ".join(result["issues"]))
    return "\n".join(lines)


def summarize_insight(notes: list[str]) -> str:
    if not notes:
        return ""
    return "AI observations (advisory):\n" + "\n".join(f"- {n}" for n in notes)
