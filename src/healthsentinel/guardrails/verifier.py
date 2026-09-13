"""Deterministic guardrail verifier (Round-3 grooming, Q13/Q14).

This is the authoritative pass/fail gate — a pure-Python re-check of raw
graph state, run *before* `critic_agent` so the (advisory, LLM-based) critic
only spends tokens on runs that are already clean. It duplicates checks that
already run inline inside `prediction_agent`/`recommendation_agent`
deliberately: this is a regression safety net (catches a future code change
that forgets to call a guardrail), not new business logic.
"""
from __future__ import annotations

import re

from .. import config
from .medical import blocked_allergen_hits, is_blocked_category, is_safe_category
from .hallucination import validate_calorie_bounds, validate_exercise_minutes

_CALORIE_RE = re.compile(r"(\d{3,5})\s*(?:kcal|cal|calories)", re.IGNORECASE)
_EXERCISE_MIN_RE = re.compile(r"(\d{1,3})\s*(?:min|minutes)[^.]{0,20}week", re.IGNORECASE)


def verify(state: dict) -> tuple[bool, list[str]]:
    """Returns (passed, issues). `passed=False` forces a nutritionist-review
    interrupt (see graph.py's `guardrail_verifier` node)."""
    issues: list[str] = []

    predictions = (state.get("prediction_result") or {}).get("predictions", [])
    for p in predictions:
        category = p.get("category", "")
        if is_blocked_category(category):
            issues.append(f"prediction category '{category}' is a blocked medical category")
        elif not is_safe_category(category):
            issues.append(f"prediction category '{category}' is not in the SAFE allowlist")
        if p.get("confidence", 0) > config.MAX_MODEL_CONFIDENCE:
            issues.append(f"prediction confidence {p.get('confidence')} exceeds cap {config.MAX_MODEL_CONFIDENCE}")

    allergies = (state.get("profile") or {}).get("allergies", [])
    recommendations = (state.get("recommendation_result") or {}).get("recommendations", [])
    for r in recommendations:
        full_text = f"{r.get('title', '')} {r.get('detail', '')}"
        hits = blocked_allergen_hits(full_text, allergies)
        if hits:
            issues.append(f"recommendation '{r.get('title')}' mentions allergen(s) {hits}")
        for match in _CALORIE_RE.finditer(full_text):
            cal_issues = validate_calorie_bounds(float(match.group(1)))
            issues.extend(f"recommendation '{r.get('title')}': {i}" for i in cal_issues)
        for match in _EXERCISE_MIN_RE.finditer(full_text):
            ex_issues = validate_exercise_minutes(float(match.group(1)))
            issues.extend(f"recommendation '{r.get('title')}': {i}" for i in ex_issues)

    medical_ctx = state.get("medical_context") or {}
    citation_user_ids = medical_ctx.get("citation_user_ids") or []
    user_id = state.get("user_id")
    mismatched = [u for u in citation_user_ids if u and u != user_id]
    if mismatched:
        issues.append(f"medical citation user_id mismatch — expected '{user_id}', got {mismatched}")

    return (len(issues) == 0, issues)
