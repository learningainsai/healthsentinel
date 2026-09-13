"""Deterministic SMS parsing (review principle: keyword/template matching
against known senders is a classifier problem, not something an LLM should
do). Extracts three signal types from a simulated SMS inbox: meal-timing
patterns (from food-delivery notifications), gym-subscription payments, and
other health-related messages.

Keyword matching is inherently approximate (e.g. "membership" could be a
magazine subscription, not a gym) — every extracted item is surfaced to the
user as a checkbox in the UI so they can rule out anything not applicable
before it ever reaches an agent. That human confirmation is the validation
boundary here, since there is no LLM call to schema-validate.
"""
from __future__ import annotations

import re
from datetime import datetime

MEAL_KEYWORDS = (
    "swiggy", "zomato", "ubereats", "uber eats", "dominos", "mcdonald",
    "starbucks", "kfc", "restaurant", "order delivered", "order from", "out for delivery",
)
GYM_KEYWORDS = ("gym", "fitness", "cult.fit", "cultfit", "yoga", "crossfit", "membership")
HEALTH_KEYWORDS = (
    "pharmacy", "hospital", "clinic", "diagnostic", "lab test", "doctor",
    "dr.", "physician", "insurance premium", "appointment", "practo", "thyrocare",
)

_AMOUNT_RE = re.compile(r"rs\.?\s?([\d,]+\.?\d*)", re.IGNORECASE)


def _matches_any(text: str, keywords: tuple[str, ...]) -> str | None:
    text_l = text.lower()
    for kw in keywords:
        if kw in text_l:
            return kw
    return None


def _meal_bucket(hour: int) -> str:
    if 5 <= hour <= 10:
        return "breakfast"
    if 11 <= hour <= 15:
        return "lunch"
    if 16 <= hour <= 18:
        return "snack"
    if 19 <= hour <= 23:
        return "dinner"
    return "late_night"


def extract_meal_timing(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        matched = _matches_any(m["body"], MEAL_KEYWORDS)
        if not matched:
            continue
        hour = datetime.fromtimestamp(m["timestamp"]).hour
        out.append({
            "id": m["id"], "type": "meal_timing", "meal_bucket": _meal_bucket(hour),
            "hour": hour, "matched_keyword": matched, "snippet": m["body"], "sender": m.get("sender", ""),
        })
    return out


def extract_gym_subscription(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        matched = _matches_any(m["body"], GYM_KEYWORDS)
        if not matched:
            continue
        amount_match = _AMOUNT_RE.search(m["body"])
        amount = float(amount_match.group(1).replace(",", "")) if amount_match else None
        out.append({
            "id": m["id"], "type": "gym_subscription", "matched_keyword": matched,
            "amount": amount, "snippet": m["body"], "sender": m.get("sender", ""),
        })
    return out


def extract_health_related(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        matched = _matches_any(m["body"], HEALTH_KEYWORDS)
        if not matched:
            continue
        out.append({
            "id": m["id"], "type": "health_related", "matched_keyword": matched,
            "snippet": m["body"], "sender": m.get("sender", ""),
        })
    return out


def parse_sms_messages(messages: list[dict]) -> dict:
    return {
        "meal_timing": extract_meal_timing(messages),
        "gym_subscription": extract_gym_subscription(messages),
        "health_related": extract_health_related(messages),
    }
