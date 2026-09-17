"""Dedicated LangGraph flow for Ask Sentinel requests."""
from __future__ import annotations

import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .agents.ask_agent import classify_question, synthesize_answer


class AskState(TypedDict, total=False):
    user_id: str
    prompt: str
    run_id: str
    profile: dict
    category: str
    needs_more_details: bool
    classification_reason: str
    analysis: dict
    audit_log: list[dict]
    errors: list[dict]
    run_cost_usd: float
    run_tokens: int


def route_after_classification(state: AskState) -> str:
    return "finish" if state.get("needs_more_details") else "synthesize"


def finish(state: AskState) -> dict:
    return {}


def build_ask_graph():
    graph = StateGraph(AskState)
    graph.add_node("classify", classify_question)
    graph.add_node("synthesize", synthesize_answer)
    graph.add_node("finish", finish)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classification,
        {"synthesize": "synthesize", "finish": "finish"},
    )
    graph.add_edge("synthesize", END)
    graph.add_edge("finish", END)
    return graph.compile()


ASK_GRAPH = build_ask_graph()


def run_ask_flow(*, user_id: str, prompt: str) -> dict:
    return ASK_GRAPH.invoke({
        "user_id": user_id,
        "prompt": prompt,
        "run_id": f"ask-{uuid.uuid4().hex[:12]}",
    })
