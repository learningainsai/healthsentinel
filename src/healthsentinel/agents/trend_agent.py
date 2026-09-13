"""Trend Agent — deterministic (no LLM) node that reads each tracked metric's
historic series from the metrics store and classifies it. This is pure
aggregation/threshold code, run as a graph node purely for wiring convenience;
`prediction_agent` is only ever handed the resulting verdicts, never the raw
series (review §1 — trend math is code, not a model call)."""
from __future__ import annotations

import time

from .. import config, metrics_store
from ..logging_utils import log_event
from ..trends import classify_all


def trend_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")

    series_by_metric = {
        metric_name: metrics_store.get_series(user_id, metric_name, window_days=config.TREND_WINDOW_DAYS)
        for metric_name in config.ALLOWED_LAB_METRICS | {"sleep_hours"}
    }
    trend_context = classify_all(series_by_metric)

    event = log_event(
        user_id=user_id, agent="trend_agent",
        input_summary={metric: len(readings) for metric, readings in series_by_metric.items()},
        decision={metric: {"verdict": t["verdict"], "flag_for_doctor": t["flag_for_doctor"]}
                  for metric, t in trend_context.items()},
        started_at=started, run_id=run_id,
    )
    return {"trend_context": trend_context, "audit_log": [event]}
