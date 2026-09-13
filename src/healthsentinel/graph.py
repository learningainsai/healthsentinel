"""LangGraph orchestration for Health Sentinel.

Why LangGraph over DeepAgents for this project (see README "Architecture
Decision" section for the full writeup): Health Sentinel's guardrails are
mostly *deterministic, code-enforced gates* (consent checks, rate limits,
blocked-category hard stops, severity-based HITL routing) wired between
several fixed, well-known agents with real parallel fan-out/fan-in — exactly
what an explicit LangGraph `StateGraph` (nodes + conditional edges +
checkpointer + `interrupt()`) is built for. DeepAgents' filesystem-and-`task`-
delegation model shines for open-ended, LLM-planned multi-step research (as in
the Career Trajectory Optimizer); it would make these hard-stop gates
implicit LLM-followed instructions rather than code-enforced graph structure,
which is not acceptable for a health-safety system.
"""
from __future__ import annotations

import time

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt

from .agents.activity_agent import activity_agent
from .agents.calendar_agent import calendar_agent
from .agents.critic_agent import critic_agent
from .agents.lab_report_agent import lab_report_agent
from .agents.medical_rag_agent import medical_rag_agent
from .agents.nutrition_agent import nutrition_agent
from .agents.prediction_agent import prediction_agent
from .agents.recommendation_agent import recommendation_agent
from .agents.sms_agent import sms_agent
from .agents.trend_agent import trend_agent
from .agents.vision_agent import vision_agent
from .guardrails.medical import MEDICAL_DISCLAIMER, append_disclaimer
from .guardrails.rate_limit import RATE_LIMITER
from .guardrails.verifier import verify
from .logging_utils import log_event
from .memory import store as mem
from .state import HealthState

NUTRITIONIST_REVIEW_SLA_HOURS = {"CRITICAL": 2, "HIGH": 8, "MEDIUM": 24, "LOW": 24}


# --- deterministic gate nodes ------------------------------------------------

def consent_gate(state: HealthState, config) -> dict:
    started = time.time()
    consent = state.get("consent", {})
    user_id = state["user_id"]
    # Thread the graph's thread_id through as run_id so every audit event can be
    # correlated and the run replayed (review §10).
    run_id = (config or {}).get("configurable", {}).get("thread_id")
    if not consent.get("tier1_core"):
        event = log_event(
            user_id=user_id, agent="consent_gate",
            input_summary=consent, decision="blocked_missing_tier1_consent",
            status="blocked", started_at=started, run_id=run_id,
        )
        return {
            "run_id": run_id,
            "blocked": True,
            "block_reason": "Tier 1 core consent (image processing, nutrition calc, "
                             "'not medical advice' acknowledgement) is required to proceed.",
            "audit_log": [event],
        }
    event = log_event(user_id=user_id, agent="consent_gate", input_summary=consent,
                       decision="tier1_consent_present", started_at=started, run_id=run_id)
    return {"run_id": run_id, "blocked": False, "audit_log": [event]}


def rate_limit_gate(state: HealthState) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    flags: list[str] = []

    if state.get("meal_image_b64"):
        ok, reason = RATE_LIMITER.allow_image(user_id)
        if not ok:
            event = log_event(user_id=user_id, agent="rate_limit_gate", input_summary={"check": "image"},
                               decision=reason, status="blocked", started_at=started, run_id=run_id)
            return {"blocked": True, "block_reason": reason, "audit_log": [event]}

    ok, reason = RATE_LIMITER.allow_analysis(user_id)
    if not ok:
        event = log_event(user_id=user_id, agent="rate_limit_gate", input_summary={"check": "analysis"},
                           decision=reason, status="blocked", started_at=started, run_id=run_id)
        return {"blocked": True, "block_reason": reason, "audit_log": [event]}

    event = log_event(user_id=user_id, agent="rate_limit_gate", input_summary={"check": "passed"},
                       decision="ok", started_at=started, run_id=run_id)
    return {"blocked": False, "guardrail_flags": flags, "audit_log": [event]}


def guardrail_gate(state: HealthState) -> dict:
    """Deterministic routing gate: decides if the nutritionist HITL review
    queue must be entered before recommendations are shown (guardrails doc §9)."""
    started = time.time()
    user_id = state["user_id"]
    reasons: list[str] = []

    prediction = state.get("prediction_result") or {}
    predictions = prediction.get("predictions", [])
    min_conf = min((p["confidence"] for p in predictions), default=1.0)
    severity = state.get("severity", "LOW")
    is_new_user = (state.get("profile") or {}).get("is_new_user", False)
    any_blocked_flag = any(f.startswith("BLOCKED_") for f in state.get("guardrail_flags", []))

    if min_conf < 0.60 and predictions:
        reasons.append(f"low_confidence_prediction ({min_conf:.2f} < 0.60)")
    if is_new_user:
        reasons.append("new_user_first_week_all_predictions_reviewed")
    if severity in {"HIGH", "CRITICAL"}:
        reasons.append(f"severity_{severity}_requires_review")
    if any_blocked_flag:
        reasons.append("a_guardrail_blocked_an_item_upstream")

    requires_review = bool(reasons)
    event = log_event(
        user_id=user_id, agent="guardrail_gate", input_summary={"min_conf": min_conf, "severity": severity},
        decision={"requires_human_review": requires_review, "reasons": reasons},
        confidence=min_conf, severity=severity, started_at=started, run_id=state.get("run_id"),
    )
    return {
        "requires_human_review": requires_review,
        "human_review_reasons": reasons,
        "review_stage": "pre_recommendation",
        "audit_log": [event],
    }


def route_after_guardrail(state: HealthState) -> str:
    return "nutritionist_review" if state.get("requires_human_review") else "recommendation_agent"


def guardrail_verifier_node(state: HealthState) -> dict:
    """Authoritative, deterministic pass/fail gate (Round-3 grooming Q13):
    re-checks raw state directly, independent of what upstream agents or the
    (advisory-only) critic concluded. Runs before critic_agent so a failing
    run never pays for the critic's reasoning-tier call."""
    started = time.time()
    user_id = state["user_id"]
    passed, issues = verify(state)
    event = log_event(
        user_id=user_id, agent="guardrail_verifier", input_summary={"checked": "predictions+recommendations+medical_citations"},
        decision={"passed": passed, "issues": issues}, status="success" if passed else "blocked",
        started_at=started, run_id=state.get("run_id"),
    )
    result: dict = {"verifier_passed": passed, "verifier_issues": issues, "audit_log": [event]}
    if not passed:
        result.update({
            "requires_human_review": True,
            "human_review_reasons": [f"deterministic_verifier_failure: {i}" for i in issues],
            "review_stage": "post_verifier",
        })
    return result


def route_after_verifier(state: HealthState) -> str:
    return "nutritionist_review" if not state.get("verifier_passed", True) else "critic_agent"


def nutritionist_review_node(state: HealthState) -> dict:
    """Human-in-the-loop pause. Resumed via `Command(resume={"decision": ...})`."""
    reasons = state.get("human_review_reasons", [])
    severity = state.get("severity", "LOW")
    sla_hours = NUTRITIONIST_REVIEW_SLA_HOURS.get(severity, 24)

    decision = interrupt({
        "reason": "nutritionist_review_required",
        "review_reasons": reasons,
        "severity": severity,
        "sla_hours": sla_hours,
        "prediction_result": state.get("prediction_result"),
        "options": ["approve", "modify", "reject", "escalate"],
    })

    user_id = state["user_id"]
    event = log_event(
        user_id=user_id, agent="nutritionist_review_node", input_summary={"reasons": reasons},
        decision=decision, severity=severity, run_id=state.get("run_id"),
    )
    return {"human_decision": decision.get("type", "approve") if isinstance(decision, dict) else str(decision),
            "audit_log": [event]}


def route_after_review(state: HealthState) -> str:
    """Two possible entry points into nutritionist_review need two different
    resume paths (Round-3 grooming Q14): a pre-recommendation review resumes
    to recommendation_agent; a post-verifier review resumes to critic_agent
    (the verifier already re-checked the recommendations directly)."""
    if state.get("human_decision") == "reject":
        return "finalize"
    stage = state.get("review_stage", "pre_recommendation")
    return "critic_agent" if stage == "post_verifier" else "recommendation_agent"


def finalize(state: HealthState) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")

    if state.get("human_decision") == "reject":
        report = "The nutritionist review team rejected this prediction/recommendation batch. No output was shown to the user."
        event = log_event(user_id=user_id, agent="finalize", input_summary={},
                          decision="rejected_by_reviewer", status="rejected", started_at=started, run_id=run_id)
        return {"final_report": append_disclaimer(report), "run_status": "rejected",
                "recovered_faults": len(state.get("errors", [])), "audit_log": [event]}

    recs = (state.get("recommendation_result") or {}).get("recommendations", [])
    predictions = (state.get("prediction_result") or {}).get("predictions", [])
    medical = state.get("medical_context") or {}
    critic = state.get("critic_review") or {}
    errors = state.get("errors", [])

    lines = ["## Daily Health Sentinel Report\n"]
    if medical.get("refused"):
        lines.append("_Medical document context was unavailable — this report was generated without it._\n")
    if predictions:
        lines.append("### Predictions")
        for p in predictions:
            lines.append(f"- **{p['category']}** ({p['confidence']:.0%} confidence, severity {p['severity']}): "
                         f"{p['statement']}\n  - _Why:_ {p['explanation']}")
    if recs:
        lines.append("\n### Recommendations")
        for r in recs:
            lines.append(f"- **{r['title']}** — {r['detail']} _(data: {r['data_support']})_")
    if not predictions and not recs:
        lines.append("No predictions met the confidence/safety bar today — nothing actionable to show.")

    # Critic is advisory-only (never overrides the deterministic verifier) but its
    # verdict is now consumed: surfaced to the user and folded into run status
    # (review §1/§7 — a critic finding is no longer silently discarded).
    critic_flagged = bool(critic) and not critic.get("passed", True)
    if critic_flagged:
        critic_issues = "; ".join(critic.get("issues", [])) or critic.get("summary", "unspecified")
        lines.append(f"\n> _Advisory (non-blocking): the reviewer critic flagged items for follow-up: {critic_issues}_")

    report = "\n".join(lines)
    final_report = append_disclaimer(report)

    degraded = bool(errors) or medical.get("refused") or critic_flagged
    run_status = "degraded" if degraded else "success"

    mem.save_progress_note(GLOBAL_STORE, user_id,
                           f"Last run severity={state.get('severity')}, status={run_status}, "
                           f"{len(predictions)} predictions, {len(recs)} recommendations.")

    event = log_event(user_id=user_id, agent="finalize",
                      input_summary={"num_predictions": len(predictions)},
                      decision={"status": run_status, "recovered_faults": len(errors),
                                "critic_passed": critic.get("passed"),
                                "run_cost_usd": round(state.get("run_cost_usd", 0.0), 6),
                                "run_tokens": state.get("run_tokens", 0)},
                      status=run_status, started_at=started, run_id=run_id,
                      cost_usd=state.get("run_cost_usd"), tokens=state.get("run_tokens"))
    return {"final_report": final_report, "run_status": run_status,
            "recovered_faults": len(errors), "audit_log": [event]}


# --- graph assembly ------------------------------------------------------------

GLOBAL_STORE = InMemoryStore()
GLOBAL_CHECKPOINTER = MemorySaver()


def build_graph():
    graph = StateGraph(HealthState)

    graph.add_node("consent_gate", consent_gate)
    graph.add_node("rate_limit_gate", rate_limit_gate)
    graph.add_node("vision_agent", vision_agent)
    graph.add_node("nutrition_agent", nutrition_agent)
    graph.add_node("medical_rag_agent", medical_rag_agent)
    graph.add_node("activity_agent", activity_agent)
    graph.add_node("sms_agent", sms_agent)
    graph.add_node("calendar_agent", calendar_agent)
    graph.add_node("lab_report_agent", lab_report_agent)
    graph.add_node("trend_agent", trend_agent)
    graph.add_node("prediction_agent", prediction_agent)
    graph.add_node("guardrail_gate", guardrail_gate)
    graph.add_node("nutritionist_review", nutritionist_review_node)
    graph.add_node("recommendation_agent", recommendation_agent)
    graph.add_node("guardrail_verifier", guardrail_verifier_node)
    graph.add_node("critic_agent", critic_agent)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("consent_gate")
    graph.add_conditional_edges("consent_gate", lambda s: "blocked" if s.get("blocked") else "ok",
                                 {"blocked": END, "ok": "rate_limit_gate"})
    graph.add_conditional_edges("rate_limit_gate", lambda s: "blocked" if s.get("blocked") else "ok",
                                 {"blocked": END, "ok": "vision_agent"})

    graph.add_edge("vision_agent", "nutrition_agent")

    # Fan-out: the "3 parallel agents" from the guardrails doc (+ sms_agent for
    # gym/meal-timing/health signals, + lab_report_agent for historic metrics).
    graph.add_edge("nutrition_agent", "medical_rag_agent")
    graph.add_edge("nutrition_agent", "activity_agent")
    graph.add_edge("nutrition_agent", "sms_agent")
    graph.add_edge("nutrition_agent", "calendar_agent")
    graph.add_edge("nutrition_agent", "lab_report_agent")

    # Fan-in: trend_agent (deterministic) waits for all five, then classifies
    # historic glucose/weight/sleep trends before prediction_agent ever runs.
    graph.add_edge("medical_rag_agent", "trend_agent")
    graph.add_edge("activity_agent", "trend_agent")
    graph.add_edge("sms_agent", "trend_agent")
    graph.add_edge("calendar_agent", "trend_agent")
    graph.add_edge("lab_report_agent", "trend_agent")
    graph.add_edge("trend_agent", "prediction_agent")

    graph.add_edge("prediction_agent", "guardrail_gate")
    graph.add_conditional_edges("guardrail_gate", route_after_guardrail,
                                 {"nutritionist_review": "nutritionist_review", "recommendation_agent": "recommendation_agent"})
    graph.add_conditional_edges("nutritionist_review", route_after_review,
                                 {"finalize": "finalize", "recommendation_agent": "recommendation_agent",
                                  "critic_agent": "critic_agent"})

    graph.add_edge("recommendation_agent", "guardrail_verifier")
    graph.add_conditional_edges("guardrail_verifier", route_after_verifier,
                                 {"nutritionist_review": "nutritionist_review", "critic_agent": "critic_agent"})
    graph.add_edge("critic_agent", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=GLOBAL_CHECKPOINTER, store=GLOBAL_STORE)
