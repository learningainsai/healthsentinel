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
