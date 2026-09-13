"""Bias detection & mitigation (guardrails doc §3).

A full statistical bias audit needs a real evaluation warehouse; here we
implement the *mechanism* the doc calls for — per-group accuracy comparison
with a variance flag — over whatever cohort stats are supplied, so the same
function works against a live metrics store in production.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_ALLOWED_VARIANCE_PCT = 5.0


@dataclass
class BiasCheckResult:
    flagged: bool
    max_variance_pct: float
    group_accuracies: dict[str, float]
    note: str


def check_demographic_bias(group_accuracies: dict[str, float]) -> BiasCheckResult:
    if not group_accuracies:
        return BiasCheckResult(False, 0.0, {}, "no cohort data available yet")
    values = list(group_accuracies.values())
    variance_pct = (max(values) - min(values)) * 100
    flagged = variance_pct > MAX_ALLOWED_VARIANCE_PCT
    note = (
        f"variance {variance_pct:.1f}% across groups exceeds {MAX_ALLOWED_VARIANCE_PCT}% — investigate"
        if flagged else "within acceptable variance"
    )
    return BiasCheckResult(flagged, variance_pct, group_accuracies, note)


def socioeconomic_guard(recommendation_text: str, is_budget_conscious: bool) -> str | None:
    """Never suggest paid supplements to a budget-conscious user; suggest whole foods instead."""
    if not is_budget_conscious:
        return None
    t = recommendation_text.lower()
    if "supplement" in t and "whole food" not in t and "budget" not in t:
        return "flagged: recommend a whole-food alternative before a paid supplement for budget-conscious users"
    return None
