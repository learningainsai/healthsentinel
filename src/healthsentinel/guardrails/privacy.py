"""Data privacy & security guardrails (guardrails doc §2) — classification + redaction helpers."""
from __future__ import annotations

TIER_1_FIELDS = {"blood_glucose", "blood_pressure", "medications", "mental_health_notes", "genetic_info"}
TIER_2_FIELDS = {"meal_images", "activity_logs", "sleep_data", "sms_messages", "calendar_events"}
TIER_3_FIELDS = {"aggregated_predictions", "trend_analysis", "model_metrics"}


def classify_field(field_name: str) -> str:
    f = field_name.strip().lower()
    if f in TIER_1_FIELDS:
        return "TIER_1_HIGHLY_SENSITIVE"
    if f in TIER_2_FIELDS:
        return "TIER_2_SENSITIVE"
    if f in TIER_3_FIELDS:
        return "TIER_3_INTERNAL"
    return "UNCLASSIFIED"


ROLE_PERMISSIONS = {
    "user": {"read_own", "export_own", "delete_own"},
    "app_agent": {"read_meal_images", "read_activity_logs", "read_medical_docs", "read_transactions"},
    "support": {"read_anonymized_errors", "assist_account"},
    "data_scientist": {"read_aggregated_anonymized"},
}


def can(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get(role, set())


def mask_account_number(account_number: str) -> str:
    digits = "".join(c for c in account_number if c.isdigit())
    return f"****{digits[-4:]}" if len(digits) >= 4 else "****"
