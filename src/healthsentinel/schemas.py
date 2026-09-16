"""Pydantic schemas for structured-output LLM calls across all agents.

Using structured output (instead of free text) is itself a guardrail: it makes
hallucinated/malformed fields impossible to smuggle past the type system, and it
gives every downstream guardrail check a stable field to validate.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class VisionResult(BaseModel):
    food_items: list[str] = Field(description="Food items identified in the meal image")
    estimated_calories: int = Field(description="Best-guess total calories for the plate")
    confidence: float = Field(description="Confidence 0.0-1.0 in the food identification")
    contains_possible_allergens: list[str] = Field(default_factory=list)
    notes: str = Field(default="", description="Anything unclear/ambiguous about the image")


class NutritionResult(BaseModel):
    total_calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    magnesium_mg: float
    iron_mg: float
    b12_mcg: float
    sodium_mg: float
    source_agreement_pct: float = Field(
        description="How closely the 3 simulated nutrition DB sources agreed (0-100)"
    )
    flags: list[str] = Field(default_factory=list)


class MappedFood(BaseModel):
    canonical_key: str = Field(description="A key from the provided allow-list (or 'generic_meal')")
    servings: float = Field(default=1.0, description="Serving multiplier for this food")


class FoodMapping(BaseModel):
    """LLM maps a free-text meal to canonical food keys ONLY — the LLM does not
    compute nutrition; deterministic code sums it (review §1)."""
    items: list[MappedFood] = Field(default_factory=list)


class LabReading(BaseModel):
    """One parameter extracted from an uploaded lab report. `metric_name` is
    validated against a fixed allowlist and `value` against physiological
    bounds before it is ever persisted (review §2 — never trust a raw model
    number into a database)."""
    metric_name: str = Field(description="e.g. 'glucose_mgdl', 'weight_kg' — must match a known metric key")
    value: float
    unit: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LabExtraction(BaseModel):
    readings: list[LabReading] = Field(default_factory=list)
    document_date: str = Field(default="", description="Date the report was issued, if stated, else empty")
    notes: str = Field(default="", description="Anything ambiguous or unread in the document")


class MedicalContext(BaseModel):
    relevant_conditions: list[str] = Field(default_factory=list)
    relevant_allergies: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float
    refused: bool = Field(default=False, description="True if evidence was insufficient to answer")
    summary: str = ""


class ActivityResult(BaseModel):
    avg_sleep_hours: float
    avg_steps: int
    exercise_minutes_this_week: int
    resting_heart_rate: int
    notes: str = ""


class CalendarResult(BaseModel):
    meetings_this_week: int
    late_night_events: int
    stress_indicator: float = Field(description="0-10 heuristic stress score from calendar density")
    notes: str = ""


class RiskDashboard(BaseModel):
    glucose_trend_risk: int = Field(ge=0, le=10)
    magnesium_deficiency_risk: int = Field(ge=0, le=10)
    sleep_deprivation_risk: int = Field(ge=0, le=10)
    stress_risk: int = Field(ge=0, le=10)
    overall_score: float = Field(ge=0.0, le=1.0)


class Prediction(BaseModel):
    category: str = Field(description="One of the SAFE prediction categories only")
    statement: str
    confidence: float
    explanation: str = Field(description="Why — the specific signals that drove this prediction")
    severity: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")


class PredictionResult(BaseModel):
    predictions: list[Prediction]
    risk_dashboard: RiskDashboard


class Recommendation(BaseModel):
    title: str
    detail: str
    data_support: str = Field(description="The specific data point(s) justifying this recommendation")


class RecommendationResult(BaseModel):
    recommendations: list[Recommendation]


class CriticReview(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    guardrail_score: float = Field(ge=0.0, le=1.0, description="Fraction of guardrail checklist items satisfied")
    summary: str


class AllergenScanItem(BaseModel):
    """Advisory-only additional allergen recall for one recommendation — the
    deterministic `blocked_allergen_hits` keyword/synonym check still runs
    independently; this only ever widens the union of hits, never narrows it."""
    title: str
    possible_allergens: list[str] = Field(
        default_factory=list,
        description="Any of the user's declared allergens that might be present, even if phrased "
                     "indirectly (e.g. a dish that typically contains it). Only choose from the "
                     "declared allergy list given — never invent a new allergen.",
    )


class AllergenScanResult(BaseModel):
    items: list[AllergenScanItem] = Field(default_factory=list)


class NormalizedAllergyTerm(BaseModel):
    """Maps a free-text allergy/condition term to the closest known category —
    normalization only; the raw term is always also kept for literal matching
    regardless of this result (review: fail open to inclusion, never exclusion)."""
    matched_category: str | None = Field(default=None, description="Closest known category, or null if none match well")
    confidence: float = Field(ge=0.0, le=1.0)


class InsightNote(BaseModel):
    observation: str = Field(description="A single cross-metric pattern, phrased as a gentle observation, never a diagnosis")
    based_on: list[str] = Field(default_factory=list, description="Which signals/trends this observation draws from")


class InsightResult(BaseModel):
    """Advisory-only cross-metric pattern spotting (review: can never change
    severity, guardrail flags, or trigger human review by itself)."""
    notes: list[InsightNote] = Field(default_factory=list, description="0-2 notable observations; empty if nothing notable")


class TextClassification(BaseModel):
    """Multi-label classification of one free-text staged note (intake_agent).
    Each field holds the portion of the note relevant to that category,
    verbatim or lightly summarized — empty string if the note says nothing
    about that category. A single note may populate more than one field."""
    meal: str = Field(default="", description="Portion about today's food/meal, empty if none")
    activity: str = Field(default="", description="Portion about exercise/sleep/steps, empty if none")
    lab: str = Field(default="", description="Portion about lab/blood-test values, empty if none")
    medical: str = Field(default="", description="Portion about medical conditions/symptoms/history, empty if none")
    sms: str = Field(default="", description="Portion about gym/food-delivery/health-related messages, empty if none")
    calendar: str = Field(default="", description="Portion about schedule/meetings/stress, empty if none")
