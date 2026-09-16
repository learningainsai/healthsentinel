"""Environment-driven configuration, incl. the multi-LLM cost-optimization router.

Different steps in the pipeline have very different accuracy/latency/cost needs:
- Vision + simple field extraction runs thousands of times/day per active user -> cheap model.
- Nutrition cross-checks / MCP-agent summarizing -> mid-tier model.
- The prediction engine and the guardrail critic are the highest-stakes, lowest-volume
  calls (they gate what a user sees) -> reasoning-tier model.

This mirrors the guardrails doc's "Rate Limiting & Resource Protection" cost ceiling
($5000/day compute) by keeping expensive models off the hot path.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=False)

_PLACEHOLDER = "your-key-here"


def is_real_key(value: str | None) -> bool:
    v = (value or "").strip()
    return bool(v) and v.lower() != _PLACEHOLDER


@dataclass(frozen=True)
class ModelRouter:
    """Maps each pipeline stage to a specific OpenAI model tier."""

    cheap: str
    mid: str
    reasoning: str
    embedding: str

    @staticmethod
    def from_env() -> "ModelRouter":
        # Pinned to dated snapshots so a silent provider-side alias update can't
        # change model behaviour without a code change (review §9).
        return ModelRouter(
            cheap=os.getenv("HEALTHSENTINEL_CHEAP_MODEL", "gpt-4o-mini-2024-07-18"),
            mid=os.getenv("HEALTHSENTINEL_MID_MODEL", "gpt-4o-mini-2024-07-18"),
            reasoning=os.getenv("HEALTHSENTINEL_REASONING_MODEL", "gpt-4o-2024-08-06"),
            embedding=os.getenv("HEALTHSENTINEL_EMBEDDING_MODEL", "text-embedding-3-small"),
        )


@dataclass(frozen=True)
class Paths:
    project_root: Path
    medical_docs_dir: Path
    grounding_dir: Path
    chroma_dir: Path
    logs_dir: Path
    metrics_db_path: Path
    sms_dir: Path
    staging_dir: Path

    @staticmethod
    def from_env() -> "Paths":
        chroma_raw = os.getenv("HEALTHSENTINEL_CHROMA_DIR", "./data/chroma")
        chroma_path = Path(chroma_raw)
        if not chroma_path.is_absolute():
            chroma_path = (PROJECT_ROOT / chroma_path).resolve()
        metrics_db_raw = os.getenv("HEALTHSENTINEL_METRICS_DB", "./data/metrics.db")
        metrics_db_path = Path(metrics_db_raw)
        if not metrics_db_path.is_absolute():
            metrics_db_path = (PROJECT_ROOT / metrics_db_path).resolve()
        return Paths(
            project_root=PROJECT_ROOT,
            medical_docs_dir=PROJECT_ROOT / "data" / "medical_docs",
            grounding_dir=PROJECT_ROOT / "data" / "grounding",
            chroma_dir=chroma_path,
            logs_dir=PROJECT_ROOT / "logs",
            metrics_db_path=metrics_db_path,
            sms_dir=PROJECT_ROOT / "data" / "sms",
            staging_dir=PROJECT_ROOT / "data" / "staging",
        )


MODELS = ModelRouter.from_env()
PATHS = Paths.from_env()
PATHS.logs_dir.mkdir(parents=True, exist_ok=True)
PATHS.metrics_db_path.parent.mkdir(parents=True, exist_ok=True)
PATHS.staging_dir.mkdir(parents=True, exist_ok=True)

# --- Guardrail thresholds (from health-sentinel-guardrails.md) -------------
CONFIDENCE_DISPLAY = 0.80         # >0.80 -> display with full recommendation
CONFIDENCE_CAUTION = 0.60         # 0.60-0.80 -> display with caution warning; <0.60 hidden
MAX_MODEL_CONFIDENCE = 0.92       # never claim near-certainty
VISION_MIN_ACCURACY = 0.85        # below this, don't trust vision output
VISION_HALLUCINATION_FLOOR = 0.50  # below this, require manual confirmation

MAX_IMAGES_PER_DAY = 10
MAX_ANALYSES_PER_DAY = 1
MAX_API_CALLS_PER_HOUR = 50

MIN_CALORIES_PER_DAY = 1200
MAX_CALORIES_PER_DAY = 3000
MAX_EXERCISE_MIN_PER_WEEK = 150

# --- Historic trend reasoning (glucose/weight/sleep over time) -------------
# Physiologically valid ranges — reject anything outside before it is ever
# persisted to the metrics store (review §2 — validate before it crosses the
# DB boundary).
WEIGHT_MIN_KG = 20.0
WEIGHT_MAX_KG = 300.0

# Only these lab-extracted metrics are ever persisted; an LLM-proposed metric
# name outside this allowlist is dropped, never written to the store.
ALLOWED_LAB_METRICS = {"glucose_mgdl", "weight_kg"}

TREND_WINDOW_DAYS = 90            # "over the last 3 months"
TREND_MIN_SAMPLES = 3             # fewer readings than this -> insufficient_data, no verdict

GLUCOSE_NORMAL_MAX_MGDL = 99.0
GLUCOSE_PREDIABETES_MAX_MGDL = 125.0   # >= this (up to diabetes) is prediabetic range
GLUCOSE_DIABETES_MIN_MGDL = 126.0
GLUCOSE_ESCALATION_DAY_FRACTION = 0.5  # >=50% of window above prediabetes threshold -> escalate

SLEEP_POOR_HOURS = 5.5
SLEEP_ESCALATION_DAY_FRACTION = 0.5

RAPID_WEIGHT_CHANGE_PCT = 5.0     # +/- 5% change within the trend window -> flag

# --- Advisory-only LLM passes (never gate a block/escalation by themselves) --
# These thresholds are the deterministic decision boundary applied to an LLM's
# output — the LLM proposes, code still decides (review: additive/normalizer
# patterns only, never a replacement for an authoritative check).
ALLERGY_NORMALIZATION_MIN_CONFIDENCE = 0.6   # below this, free-text term is kept literal-only, not mapped to a category
REJECTED_RECOMMENDATION_SIMILARITY_THRESHOLD = 0.85  # cosine similarity to an already-rejected title

# --- Cost controls (review §9) ---------------------------------------------
# Hard per-run spend cap; a run that reaches it short-circuits to a degraded
# finalize instead of continuing to call paid models. 0 disables the cap.
MAX_RUN_COST_USD = float(os.getenv("HEALTHSENTINEL_MAX_RUN_COST_USD", "0.50"))

# USD per 1M tokens (input, output), keyed by resolved (dated) model id.
MODEL_PRICES_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o": (2.50, 10.00),
}


def price_for(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for a single call; unknown models price at 0 (logged, not billed)."""
    rates = MODEL_PRICES_PER_1M.get(model)
    if not rates:
        # tolerate provider suffixes like "gpt-4o-2024-08-06" already covered;
        # fall back to a prefix match before giving up.
        for known, known_rates in MODEL_PRICES_PER_1M.items():
            if model.startswith(known):
                rates = known_rates
                break
    if not rates:
        return 0.0
    in_rate, out_rate = rates
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate
