"""LLM factory + instrumented structured-output calls.

`call_structured` is the single choke point for every model call: it enforces
the per-run spend cap, captures tokens/cost/model-id/stop_reason/request-id for
the trace (review §10), and converts an unusable response into a typed
`ModelOutputError` instead of silently returning a partial object (review §2).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from . import config
from .budget import COST_TRACKER
from .faults import Fault, FaultClass, Layer, ModelOutputError

_OK_STOP_REASONS = {None, "stop", "tool_calls", "function_call", "end_turn"}


@lru_cache(maxsize=8)
def get_llm(tier: str, temperature: float = 0.0) -> ChatOpenAI:
    model_name = {
        "cheap": config.MODELS.cheap,
        "mid": config.MODELS.mid,
        "reasoning": config.MODELS.reasoning,
    }[tier]
    return ChatOpenAI(model=model_name, temperature=temperature, max_retries=3, timeout=60)


@dataclass
class LLMCallResult:
    parsed: Any
    model: str
    prompt_version: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    stop_reason: str | None
    request_id: str | None

    def trace_fields(self) -> dict:
        return {
            "model": self.model,
            "prompt_version": self.prompt_version,
            "tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "stop_reason": self.stop_reason,
            "provider_request_id": self.request_id,
        }


def call_structured(
    tier: str,
    schema: type,
    messages: list,
    *,
    run_id: str | None = None,
    prompt_version: str | None = None,
) -> LLMCallResult:
    """Invoke a structured-output model call, capturing usage and validating the
    stop reason. Raises `ModelOutputError` (typed) on a bad/empty response and
    `BudgetExceeded` (typed) if the run's spend cap is already reached."""
    COST_TRACKER.ensure_under_cap(run_id)

    llm = get_llm(tier).with_structured_output(schema, include_raw=True)
    out = llm.invoke(messages)

    raw = out.get("raw")
    parsed = out.get("parsed")
    parsing_error = out.get("parsing_error")

    meta = getattr(raw, "response_metadata", {}) or {}
    usage = getattr(raw, "usage_metadata", None) or {}
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
    model = meta.get("model_name") or get_llm(tier).model_name
    stop_reason = meta.get("finish_reason")
    request_id = getattr(raw, "id", None)
    cost = config.price_for(model, prompt_tokens, completion_tokens)

    COST_TRACKER.add(run_id, cost, total_tokens)

    if parsing_error or parsed is None:
        raise ModelOutputError(Fault(
            layer=Layer.LLM, fault_class=FaultClass.SCHEMA_VALIDATION,
            message=str(parsing_error or "empty structured output"),
            model=model, stop_reason=stop_reason, request_id=request_id,
        ))
    if stop_reason not in _OK_STOP_REASONS:
        fault_class = FaultClass.CONTENT_FILTER if stop_reason == "content_filter" else FaultClass.TRUNCATION
        raise ModelOutputError(Fault(
            layer=Layer.LLM, fault_class=fault_class,
            message=f"unusable stop_reason={stop_reason}",
            model=model, stop_reason=stop_reason, request_id=request_id,
        ))

    return LLMCallResult(
        parsed=parsed, model=model, prompt_version=prompt_version,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=total_tokens, cost_usd=cost,
        stop_reason=stop_reason, request_id=request_id,
    )
