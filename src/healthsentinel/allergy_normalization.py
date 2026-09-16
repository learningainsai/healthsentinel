"""Free-text allergy/condition normalization — an LLM classification helper
used from the UI *before* the graph runs (not a graph node), mirroring how
`sms_parser` pre-processes raw input.

Safety contract (review: fail open to inclusion, never exclusion): the raw
term the user typed is always returned alongside any mapped category, so a
low-confidence or failed mapping still gets checked literally by
`guardrails.medical.blocked_allergen_hits` downstream — normalization can only
ever add a synonym-expanded category, never drop the user's original term.
"""
from __future__ import annotations

from . import config
from .prompts import ALLERGY_NORMALIZATION
from .schemas import NormalizedAllergyTerm


def normalize_free_text_term(term: str, known_categories: list[str], *, run_id: str | None = None) -> list[str]:
    """Returns the terms to add to the user's allergy/condition list: always
    the raw term, plus the mapped known category if confidence clears the bar.
    Falls back to literal-only on any LLM/parsing failure (never blocks the run)."""
    term = term.strip()
    if not term:
        return []
    try:
        from .llm import call_structured  # local import: keep this module import-light for app.py startup

        call = call_structured(
            "cheap", NormalizedAllergyTerm,
            [("system", ALLERGY_NORMALIZATION.text),
             ("human", f"Known categories: {known_categories}\nFree-text term: {term!r}")],
            run_id=run_id, prompt_version=ALLERGY_NORMALIZATION.version,
        )
        result: NormalizedAllergyTerm = call.parsed
        if result.matched_category and result.confidence >= config.ALLERGY_NORMALIZATION_MIN_CONFIDENCE:
            return [term, result.matched_category]
        return [term]
    except Exception:
        return [term]
