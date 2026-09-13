"""Hallucination detection & recommendation-bounds guardrails (guardrails doc §3)."""
from __future__ import annotations

from .. import config


def cap_confidence(score: float, max_allowed: float = config.MAX_MODEL_CONFIDENCE) -> tuple[float, str | None]:
    if score > max_allowed:
        return max_allowed, "Very high confidence — capped and flagged for doctor consultation"
    return score, None


def validate_calorie_bounds(calories: float) -> list[str]:
    issues = []
    if calories < config.MIN_CALORIES_PER_DAY:
        issues.append(f"calorie suggestion {calories} below safe floor {config.MIN_CALORIES_PER_DAY}")
    if calories > config.MAX_CALORIES_PER_DAY:
        issues.append(f"calorie suggestion {calories} above safe ceiling {config.MAX_CALORIES_PER_DAY}")
    return issues


def validate_exercise_minutes(minutes_per_week: float) -> list[str]:
    if minutes_per_week > config.MAX_EXERCISE_MIN_PER_WEEK:
        return [f"exercise suggestion {minutes_per_week} min/week exceeds safe ceiling {config.MAX_EXERCISE_MIN_PER_WEEK}"]
    return []


UNPROVEN_SUPPLEMENT_KEYWORDS = {"mlm", "miracle cure", "detox tea", "fat burner pill", "unregulated supplement"}
EXTREME_DIET_KEYWORDS = {"carnivore", "zero-carb", "water fast", "extended fast"}


def reject_unusual_recommendation(text: str) -> str | None:
    t = text.lower()
    for kw in UNPROVEN_SUPPLEMENT_KEYWORDS:
        if kw in t:
            return f"rejected: mentions unproven supplement pattern '{kw}'"
    for kw in EXTREME_DIET_KEYWORDS:
        if kw in t:
            return f"rejected: mentions extreme/unapproved diet pattern '{kw}' without medical approval"
    return None


def vision_requires_manual_confirmation(confidence: float) -> bool:
    return confidence < config.VISION_HALLUCINATION_FLOOR
