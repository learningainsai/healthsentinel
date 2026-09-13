"""Deterministic trend classification over historic metric series (review
principle: aggregation/threshold-duration math is code, never an LLM guess).

The LLM downstream (`prediction_agent`) is only ever given the `TrendResult` it
produces here and told to phrase it — it never sees the raw series and never
computes a verdict itself.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from . import config
from .metrics_store import MetricReading

Verdict = str  # "insufficient_data" | "improving" | "stable" | "worsening"


@dataclass
class TrendResult:
    metric_name: str
    verdict: Verdict
    evidence: str
    flag_for_doctor: bool = False
    window_days: int = 0
    sample_count: int = 0
    latest_value: float | None = None
    mean_value: float | None = None
    baseline_value: float | None = None


def _insufficient(metric_name: str, sample_count: int) -> TrendResult:
    return TrendResult(
        metric_name=metric_name, verdict="insufficient_data",
        evidence=f"only {sample_count} reading(s) in the last {config.TREND_WINDOW_DAYS} days "
                 f"(need >= {config.TREND_MIN_SAMPLES}) — not enough history for a trend yet.",
        window_days=config.TREND_WINDOW_DAYS, sample_count=sample_count,
    )


def classify_glucose_trend(readings: list[MetricReading]) -> TrendResult:
    n = len(readings)
    if n < config.TREND_MIN_SAMPLES:
        return _insufficient("glucose_mgdl", n)

    values = [r.value for r in readings]
    mean_value = statistics.fmean(values)
    days_above = sum(1 for v in values if v >= config.GLUCOSE_PREDIABETES_MAX_MGDL)
    fraction_above = days_above / n
    latest = values[-1]
    first_half = values[: n // 2] or values
    second_half = values[n // 2 :] or values
    trend_delta = statistics.fmean(second_half) - statistics.fmean(first_half)

    if fraction_above >= config.GLUCOSE_ESCALATION_DAY_FRACTION:
        verdict = "worsening" if trend_delta >= 0 else "improving"
        flag = True
        evidence = (
            f"{fraction_above:.0%} of {n} glucose readings over the last {config.TREND_WINDOW_DAYS} days "
            f"were at/above {config.GLUCOSE_PREDIABETES_MAX_MGDL:.0f} mg/dL (mean {mean_value:.0f} mg/dL, "
            f"latest {latest:.0f} mg/dL) — sustained elevation, consult a doctor."
        )
    else:
        verdict = "stable"
        flag = False
        evidence = (
            f"{n} glucose readings over the last {config.TREND_WINDOW_DAYS} days average {mean_value:.0f} mg/dL "
            f"(latest {latest:.0f} mg/dL), within the normal/borderline range — looks stable."
        )
    return TrendResult(
        metric_name="glucose_mgdl", verdict=verdict, evidence=evidence, flag_for_doctor=flag,
        window_days=config.TREND_WINDOW_DAYS, sample_count=n, latest_value=latest, mean_value=mean_value,
    )


def classify_weight_trend(readings: list[MetricReading]) -> TrendResult:
    n = len(readings)
    if n < config.TREND_MIN_SAMPLES:
        return _insufficient("weight_kg", n)

    values = [r.value for r in readings]
    baseline = values[0]
    latest = values[-1]
    mean_value = statistics.fmean(values)
    pct_change = ((latest - baseline) / baseline) * 100 if baseline else 0.0

    if abs(pct_change) >= config.RAPID_WEIGHT_CHANGE_PCT:
        verdict = "worsening"
        flag = True
        direction = "loss" if pct_change < 0 else "gain"
        evidence = (
            f"weight changed {pct_change:+.1f}% (rapid {direction}) over the last {config.TREND_WINDOW_DAYS} days "
            f"({baseline:.1f}kg -> {latest:.1f}kg) — unexplained rapid change, consult a doctor."
        )
    else:
        verdict = "stable"
        flag = False
        evidence = (
            f"weight changed {pct_change:+.1f}% over the last {config.TREND_WINDOW_DAYS} days "
            f"({baseline:.1f}kg -> {latest:.1f}kg) — looks stable."
        )
    return TrendResult(
        metric_name="weight_kg", verdict=verdict, evidence=evidence, flag_for_doctor=flag,
        window_days=config.TREND_WINDOW_DAYS, sample_count=n, latest_value=latest, mean_value=mean_value,
        baseline_value=baseline,
    )


def classify_sleep_trend(readings: list[MetricReading]) -> TrendResult:
    n = len(readings)
    if n < config.TREND_MIN_SAMPLES:
        return _insufficient("sleep_hours", n)

    values = [r.value for r in readings]
    mean_value = statistics.fmean(values)
    latest = values[-1]
    nights_poor = sum(1 for v in values if v < config.SLEEP_POOR_HOURS)
    fraction_poor = nights_poor / n

    if fraction_poor >= config.SLEEP_ESCALATION_DAY_FRACTION:
        verdict = "worsening"
        flag = True
        evidence = (
            f"{fraction_poor:.0%} of {n} nights over the last {config.TREND_WINDOW_DAYS} days were below "
            f"{config.SLEEP_POOR_HOURS}h (mean {mean_value:.1f}h) — sustained poor sleep, consult a doctor."
        )
    else:
        verdict = "stable"
        flag = False
        evidence = (
            f"{n} nights over the last {config.TREND_WINDOW_DAYS} days average {mean_value:.1f}h sleep "
            f"(latest {latest:.1f}h) — looks stable."
        )
    return TrendResult(
        metric_name="sleep_hours", verdict=verdict, evidence=evidence, flag_for_doctor=flag,
        window_days=config.TREND_WINDOW_DAYS, sample_count=n, latest_value=latest, mean_value=mean_value,
    )


CLASSIFIERS = {
    "glucose_mgdl": classify_glucose_trend,
    "weight_kg": classify_weight_trend,
    "sleep_hours": classify_sleep_trend,
}


def classify_all(series_by_metric: dict[str, list[MetricReading]]) -> dict[str, dict]:
    """Runs every known classifier against whatever series are available and
    returns `{metric_name: TrendResult.__dict__}` for use as LangGraph state
    (plain dicts, not dataclasses, per this repo's state convention)."""
    results: dict[str, dict] = {}
    for metric_name, classifier in CLASSIFIERS.items():
        readings = series_by_metric.get(metric_name, [])
        result = classifier(readings)
        results[metric_name] = result.__dict__
    return results
