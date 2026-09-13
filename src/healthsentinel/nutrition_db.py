"""Deterministic nutrition table + summation (review §1).

Nutrition arithmetic is a lookup + sum, not a reasoning task, so it is done in
code. The LLM's only job upstream is mapping free-text food descriptions to the
canonical keys below; every number here is fixed and unit-testable.

Values are approximate per-serving figures for a demo corpus, not clinical data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FoodNutrition:
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    magnesium_mg: float
    iron_mg: float
    b12_mcg: float
    sodium_mg: float


# Canonical key -> per-serving nutrition.
FOOD_DB: dict[str, FoodNutrition] = {
    "chicken_breast": FoodNutrition(165, 31.0, 0.0, 3.6, 29, 1.0, 0.3, 74),
    "salmon": FoodNutrition(208, 20.0, 0.0, 13.0, 30, 0.8, 3.2, 59),
    "egg": FoodNutrition(78, 6.3, 0.6, 5.3, 6, 0.9, 0.6, 62),
    "brown_rice": FoodNutrition(216, 5.0, 45.0, 1.8, 84, 0.8, 0.0, 10),
    "white_rice": FoodNutrition(205, 4.3, 45.0, 0.4, 19, 1.9, 0.0, 2),
    "pasta": FoodNutrition(221, 8.1, 43.0, 1.3, 25, 1.8, 0.0, 1),
    "bread": FoodNutrition(79, 2.7, 14.0, 1.0, 7, 0.9, 0.0, 152),
    "potato": FoodNutrition(163, 4.3, 37.0, 0.2, 48, 1.9, 0.0, 13),
    "oatmeal": FoodNutrition(158, 6.0, 27.0, 3.2, 61, 2.1, 0.0, 115),
    "broccoli": FoodNutrition(55, 3.7, 11.0, 0.6, 33, 1.0, 0.0, 33),
    "spinach": FoodNutrition(23, 2.9, 3.6, 0.4, 79, 2.7, 0.0, 79),
    "mixed_vegetables": FoodNutrition(72, 3.6, 15.0, 0.4, 30, 1.3, 0.0, 60),
    "salad": FoodNutrition(45, 2.0, 6.0, 1.5, 20, 1.0, 0.0, 30),
    "banana": FoodNutrition(105, 1.3, 27.0, 0.4, 32, 0.3, 0.0, 1),
    "apple": FoodNutrition(95, 0.5, 25.0, 0.3, 9, 0.2, 0.0, 2),
    "berries": FoodNutrition(57, 0.7, 14.0, 0.3, 22, 0.4, 0.0, 1),
    "peanut_butter": FoodNutrition(188, 8.0, 6.0, 16.0, 57, 0.6, 0.0, 152),
    "almonds": FoodNutrition(164, 6.0, 6.0, 14.0, 76, 1.1, 0.0, 1),
    "milk": FoodNutrition(103, 8.0, 12.0, 2.4, 24, 0.1, 1.3, 107),
    "yogurt": FoodNutrition(149, 8.5, 11.0, 8.0, 19, 0.1, 1.1, 113),
    "cheese": FoodNutrition(113, 7.0, 0.9, 9.0, 8, 0.1, 0.4, 180),
    "generic_meal": FoodNutrition(350, 15.0, 40.0, 12.0, 45, 2.0, 0.5, 500),
}

ALLOWED_FOOD_KEYS = sorted(FOOD_DB.keys())

_NUTRIENT_FIELDS = (
    "calories", "protein_g", "carbs_g", "fat_g",
    "magnesium_mg", "iron_mg", "b12_mcg", "sodium_mg",
)


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def compute_nutrition(mapped_items: list[tuple[str, float]]) -> tuple[dict, list[str], float]:
    """Sums per-serving nutrition across mapped (canonical_key, servings) pairs.

    Returns (totals, flags, coverage_pct). `coverage_pct` is the share of
    described items that resolved to a real DB key (deterministic mapping
    quality signal — replaces the old fake "3-source agreement").
    """
    totals: dict[str, float] = {f: 0.0 for f in _NUTRIENT_FIELDS}
    flags: list[str] = []
    matched = 0
    for raw_key, servings in mapped_items:
        food = FOOD_DB.get(_normalize_key(raw_key))
        if food is None:
            flags.append(f"unmapped_food:{raw_key}")
            continue
        matched += 1
        servings = max(0.0, float(servings))
        for field_name in _NUTRIENT_FIELDS:
            totals[field_name] += getattr(food, field_name) * servings

    coverage_pct = round(100.0 * matched / len(mapped_items), 1) if mapped_items else 0.0
    result = {
        "total_calories": int(round(totals["calories"])),
        "protein_g": round(totals["protein_g"], 1),
        "carbs_g": round(totals["carbs_g"], 1),
        "fat_g": round(totals["fat_g"], 1),
        "magnesium_mg": round(totals["magnesium_mg"], 1),
        "iron_mg": round(totals["iron_mg"], 1),
        "b12_mcg": round(totals["b12_mcg"], 1),
        "sodium_mg": round(totals["sodium_mg"], 1),
        "source_agreement_pct": coverage_pct,
        "flags": flags,
    }
    return result, flags, coverage_pct
