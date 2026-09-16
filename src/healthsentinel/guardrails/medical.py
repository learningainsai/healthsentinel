"""Medical & clinical guardrails (guardrails doc §1).

These are deterministic, code-enforced gates — never left to an LLM's
discretion — because they are the hard stops that must never be bypassed.
"""
from __future__ import annotations

from dataclasses import dataclass

BLOCKED_CATEGORIES = {
    "heart_disease", "cancer", "severe_infection", "psychiatric",
    "emergency", "stroke", "cardiac_arrest", "sepsis",
    "pregnancy", "pediatric",
}

SAFE_CATEGORIES = {
    "nutritional_deficiency", "lifestyle_trend", "prediabetes_trend",
    "general_wellness", "symptom_tracking",
}

MEDICAL_DISCLAIMER = """\
⚠️  IMPORTANT DISCLAIMER

Health Sentinel is NOT a medical diagnosis tool. It is designed for
nutritional tracking and lifestyle optimization only. Predictions are based
on lifestyle patterns, NOT medical science. This app does NOT replace:
  • Doctor visits or medical consultations
  • Professional medical diagnosis
  • Prescription medications or treatments
  • Mental health professional care

If you experience symptoms, consult a healthcare provider.
If experiencing a medical emergency, call 911 immediately.

Risk scores are educational estimates ONLY, not clinical guidance.
"""


def is_blocked_category(category: str) -> bool:
    return category.strip().lower().replace(" ", "_") in BLOCKED_CATEGORIES


def is_safe_category(category: str) -> bool:
    """Allowlist check: a prediction category is valid ONLY if it is in the
    SAFE set. Preferred over `is_blocked_category` (a denylist), which lets an
    unknown category (in neither set) slip through (review §2)."""
    return category.strip().lower().replace(" ", "_") in SAFE_CATEGORIES


def confidence_action(confidence: float, cfg) -> str:
    """Returns 'display' | 'caution' | 'hide' per the confidence-threshold table."""
    if confidence > cfg.CONFIDENCE_DISPLAY:
        return "display"
    if confidence >= cfg.CONFIDENCE_CAUTION:
        return "caution"
    return "hide"


@dataclass
class SeverityResult:
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    reasons: list[str]


def severity_from_signals(*, glucose_mgdl: float | None, sleep_hours: float | None,
                           magnesium_deficient: bool, stress_score: float | None,
                           extreme_weight_loss: bool = False) -> SeverityResult:
    """Escalation protocol table from guardrails doc §1."""
    reasons: list[str] = []
    if (glucose_mgdl is not None and glucose_mgdl > 180) or extreme_weight_loss:
        reasons.append("glucose > 180 mg/dL or extreme weight loss detected")
        return SeverityResult("CRITICAL", reasons)
    if glucose_mgdl is not None and glucose_mgdl >= 120:
        reasons.append("glucose trending >= 120 mg/dL")
    if sleep_hours is not None and sleep_hours < 5.5:
        reasons.append("poor sleep (< 5.5h average)")
    if reasons:
        return SeverityResult("HIGH", reasons)
    if magnesium_deficient:
        reasons.append("magnesium deficiency detected")
    if stress_score is not None and 3.0 <= stress_score < 6.0:
        reasons.append("mild stress elevation")
    if reasons:
        return SeverityResult("MEDIUM", reasons)
    return SeverityResult("LOW", ["normal ranges — no escalation triggers"])


def append_disclaimer(report_text: str) -> str:
    return f"{report_text.rstrip()}\n\n---\n{MEDICAL_DISCLAIMER}"


def adjust_for_medical_history(conditions: list[str]) -> dict:
    """Adjust prediction weighting / urgency based on existing conditions."""
    conditions_l = {c.strip().lower() for c in conditions}
    adjustments = {"glucose_weight_multiplier": 1.0, "sodium_flag_threshold_mg": 2300,
                   "doctor_appt_urgency_bump": False}
    if "prediabetes" in conditions_l:
        adjustments["glucose_weight_multiplier"] = 1.5
        adjustments["doctor_appt_urgency_bump"] = True
    if "hypertension" in conditions_l:
        adjustments["sodium_flag_threshold_mg"] = 2300
    return adjustments


ALLERGEN_SYNONYMS: dict[str, list[str]] = {
    "peanuts": ["peanut", "groundnut", "groundnuts", "cacahuete", "arachide"],
    "shellfish": ["shrimp", "prawn", "prawns", "crab", "lobster", "crevette"],
    "soy": ["soya", "soybean", "edamame"],
    "dairy": ["milk", "cheese", "lactose", "butter", "cream"],
    "gluten": ["wheat", "barley", "rye", "seitan"],
}


def blocked_allergen_hits(text: str, allergies: list[str]) -> list[str]:
    """Matches allergens by name or known synonym/translation/misspelling so
    filtering isn't defeated by e.g. 'groundnut' when the allergy is 'peanuts'."""
    text_l = text.lower()
    hits = []
    for a in allergies:
        a_l = a.strip().lower()
        terms = [a_l, *ALLERGEN_SYNONYMS.get(a_l, [])]
        if any(term in text_l for term in terms):
            hits.append(a)
    return hits


# Fixed taxonomy for free-text allergy normalization (app.py) — an LLM may only
# ever map a free-text term onto one of these, never invent a new category.
KNOWN_ALLERGY_CATEGORIES = sorted(ALLERGEN_SYNONYMS.keys())
