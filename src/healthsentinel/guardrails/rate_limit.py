"""Rate limiting & poison-data (anomaly) detection (guardrails doc §5)."""
from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque

from .. import config


class RateLimiter:
    """In-memory per-user rate limiter (swap for Redis in production)."""

    def __init__(self) -> None:
        self._images_today: dict[str, list[float]] = defaultdict(list)
        self._analyses_today: dict[str, list[float]] = defaultdict(list)
        self._api_calls_hour: dict[str, deque] = defaultdict(deque)

    @staticmethod
    def _prune(bucket, window_s: float) -> None:
        cutoff = time.time() - window_s
        while bucket and bucket[0] < cutoff:
            bucket.pop(0) if isinstance(bucket, list) else bucket.popleft()

    def allow_image(self, user_id: str) -> tuple[bool, str | None]:
        bucket = self._images_today[user_id]
        self._prune(bucket, 86400)
        if len(bucket) >= config.MAX_IMAGES_PER_DAY:
            return False, f"Rate limit reached: max {config.MAX_IMAGES_PER_DAY} meal images/day"
        bucket.append(time.time())
        return True, None

    def allow_analysis(self, user_id: str) -> tuple[bool, str | None]:
        bucket = self._analyses_today[user_id]
        self._prune(bucket, 86400)
        if len(bucket) >= config.MAX_ANALYSES_PER_DAY:
            return False, f"Rate limit reached: max {config.MAX_ANALYSES_PER_DAY} end-of-day analysis/day"
        bucket.append(time.time())
        return True, None

    def allow_api_call(self, user_id: str) -> tuple[bool, str | None]:
        bucket = self._api_calls_hour[user_id]
        self._prune(bucket, 3600)
        if len(bucket) >= config.MAX_API_CALLS_PER_HOUR:
            return False, "Rate limit reached. Try again in 1 hour."
        bucket.append(time.time())
        return True, None


RATE_LIMITER = RateLimiter()

_USER_HISTORY: dict[str, list[float]] = defaultdict(list)


def is_anomalous(user_id: str, metric_name: str, value: float, sigma: float = 3.0) -> tuple[bool, str | None]:
    """3-sigma anomaly detection against a user's own rolling history for one metric."""
    key = f"{user_id}:{metric_name}"
    history = _USER_HISTORY[key]
    if len(history) < 5:
        history.append(value)
        return False, None
    mean = statistics.fmean(history)
    stdev = statistics.pstdev(history) or 1.0
    z = abs(value - mean) / stdev
    history.append(value)
    if len(history) > 60:
        history.pop(0)
    if z > sigma:
        return True, f"{metric_name}={value} is {z:.1f} std-devs from the user's average ({mean:.1f}) — flagged for manual review"
    return False, None


def is_physiologically_invalid(metric_name: str, value: float) -> str | None:
    bounds = {
        "blood_glucose_mgdl": (0, 600),
        "glucose_mgdl": (0, 600),
        "calories": (0, 15000),
        "sleep_hours": (0, 24),
        "weight_kg": (config.WEIGHT_MIN_KG, config.WEIGHT_MAX_KG),
    }
    lo, hi = bounds.get(metric_name, (None, None))
    if lo is None:
        return None
    if metric_name in ("blood_glucose_mgdl", "glucose_mgdl") and value <= 0:
        return f"{metric_name}={value} is invalid (<=0) — rejected"
    if not (lo <= value <= hi):
        return f"{metric_name}={value} is outside a physiologically valid range ({lo}, {hi}) — rejected"
    return None
