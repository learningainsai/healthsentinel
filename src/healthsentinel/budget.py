"""Per-run spend cap (review §9).

In-memory, keyed by run_id — same posture as the module-global RateLimiter.
Swap the dict for Redis in production without touching call sites.
"""
from __future__ import annotations

from collections import defaultdict

from . import config
from .faults import Fault, FaultClass, Layer, TypedError


class BudgetExceeded(TypedError):
    """Raised when a run's accumulated LLM spend reaches the configured cap."""


class CostTracker:
    def __init__(self) -> None:
        self._cost_by_run: dict[str, float] = defaultdict(float)
        self._tokens_by_run: dict[str, int] = defaultdict(int)

    def add(self, run_id: str | None, cost_usd: float, tokens: int = 0) -> None:
        if not run_id:
            return
        self._cost_by_run[run_id] += cost_usd
        self._tokens_by_run[run_id] += tokens

    def cost(self, run_id: str | None) -> float:
        return self._cost_by_run.get(run_id or "", 0.0)

    def tokens(self, run_id: str | None) -> int:
        return self._tokens_by_run.get(run_id or "", 0)

    def ensure_under_cap(self, run_id: str | None, cap_usd: float | None = None) -> None:
        cap = config.MAX_RUN_COST_USD if cap_usd is None else cap_usd
        if not run_id or cap <= 0:
            return
        spent = self._cost_by_run.get(run_id, 0.0)
        if spent >= cap:
            raise BudgetExceeded(Fault(
                layer=Layer.ORCHESTRATION,
                fault_class=FaultClass.BUDGET_EXCEEDED,
                message=f"run spend ${spent:.4f} reached cap ${cap:.2f}",
                context={"run_id": run_id, "spent_usd": round(spent, 4), "cap_usd": cap},
            ))

    def reset(self, run_id: str) -> None:
        self._cost_by_run.pop(run_id, None)
        self._tokens_by_run.pop(run_id, None)


COST_TRACKER = CostTracker()
