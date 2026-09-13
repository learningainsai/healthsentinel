"""Typed fault taxonomy for failure attribution (review §10).

A fault carries the owning layer and a fault class so distinct failures
(timeout vs. schema vs. content-filter vs. budget) are never collapsed into a
single generic error string in the trace.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Layer(str, Enum):
    AGENT = "agent"
    GUARDRAIL = "guardrail"
    RAG = "rag"
    LLM = "llm"
    TOOL = "tool"
    ORCHESTRATION = "orchestration"


class FaultClass(str, Enum):
    TIMEOUT = "timeout"
    TRUNCATION = "truncation"
    CONTENT_FILTER = "content_filter"
    SCHEMA_VALIDATION = "schema_validation"
    PROVIDER_ERROR = "provider_error"
    RETRIEVAL = "retrieval"
    BUDGET_EXCEEDED = "budget_exceeded"
    UNKNOWN = "unknown"


@dataclass
class Fault:
    layer: Layer
    fault_class: FaultClass
    message: str
    model: str | None = None
    stop_reason: str | None = None
    request_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "layer": self.layer.value,
            "fault_class": self.fault_class.value,
            "message": self.message,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "request_id": self.request_id,
            **({"context": self.context} if self.context else {}),
        }


class TypedError(Exception):
    """Base exception that carries a `Fault`, so the original fault class is
    never lost as the error propagates and is re-wrapped."""

    def __init__(self, fault: Fault) -> None:
        super().__init__(fault.message)
        self.fault = fault


class ModelOutputError(TypedError):
    """Raised when a model response is unusable (bad stop_reason, schema
    validation failure, or empty structured output)."""


def classify_exception(exc: Exception, *, layer: Layer = Layer.AGENT) -> Fault:
    """Best-effort mapping from an arbitrary exception to a typed fault, so a
    recovered failure still lands in the trace with a real fault class."""
    if isinstance(exc, TypedError):
        return exc.fault
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text:
        fault_class = FaultClass.TIMEOUT
    elif "content_filter" in text or "content policy" in text:
        fault_class = FaultClass.CONTENT_FILTER
    elif "ratelimit" in name or "rate limit" in text or "apierror" in name or "connection" in name:
        fault_class = FaultClass.PROVIDER_ERROR
    elif "validation" in name or "pydantic" in text:
        fault_class = FaultClass.SCHEMA_VALIDATION
    else:
        fault_class = FaultClass.UNKNOWN
    return Fault(layer=layer, fault_class=fault_class, message=f"{type(exc).__name__}: {exc}")
