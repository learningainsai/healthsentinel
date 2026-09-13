"""Agent 3 — Medical RAG Agent: answers from the user's medical documents only
(RAG over Chroma), with an explicit refusal path when evidence is weak.

Guardrail: if Google-Drive/medical context is unavailable, continue without
it, reduce downstream confidence by 20%, and add a disclaimer (guardrails
doc §5 — graceful degradation), rather than fabricating medical facts.
"""
from __future__ import annotations

import time

from .. import config
from ..faults import Layer, classify_exception
from ..llm import call_structured
from ..logging_utils import log_event
from ..prompts import MEDICAL_RAG
from ..rag.retrieval import REFUSAL_MIN_SCORE, retrieve
from ..schemas import MedicalContext


def _retrieval_trace(chunks, user_id: str) -> dict:
    """Candidate IDs/scores + the filter, index, and embedding model — without
    these a wrong medical answer can't be attributed to retrieval (review §10)."""
    return {
        "candidate_chunk_ids": [c.metadata.get("chunk_id") for c in chunks],
        "scores": [round(c.score, 4) for c in chunks],
        "filter": {"user_id": user_id},
        "embedding_model": config.MODELS.embedding,
        "index_collection": "health_sentinel_medical_docs",
        "refusal_min_score": REFUSAL_MIN_SCORE,
    }


def medical_rag_agent(state: dict) -> dict:
    started = time.time()
    user_id = state["user_id"]
    run_id = state.get("run_id")
    query = state.get("medical_query") or "Summarize conditions, allergies, and any relevant lab flags for daily nutrition/lifestyle coaching."

    try:
        chunks, refused = retrieve(query, user_id=user_id, k=4)
        retrieval_trace = _retrieval_trace(chunks, user_id)
        if refused or not chunks:
            event = log_event(
                user_id=user_id, agent="medical_rag_agent",
                input_summary={"query": query}, decision="refused_insufficient_evidence",
                confidence=0.0, started_at=started, status="refused",
                run_id=run_id, retrieval=retrieval_trace,
            )
            return {
                "medical_context": MedicalContext(confidence=0.0, refused=True,
                                                   summary="No medical document evidence available — continuing without medical context.").model_dump(),
                "guardrail_flags": ["medical_context_unavailable_confidence_reduced_20pct"],
                "audit_log": [event],
            }

        evidence_text = "\n\n".join(f"[{c.metadata.get('section_path', '?')}] {c.text}" for c in chunks)
        call = call_structured(
            "mid", MedicalContext,
            [("system", MEDICAL_RAG.text), ("human", f"Question: {query}\n\nEvidence:\n{evidence_text}")],
            run_id=run_id, prompt_version=MEDICAL_RAG.version,
        )
        result: MedicalContext = call.parsed
        # Citations tied to real chunk IDs, not reconstructed strings (review §6).
        result.citations = [c.metadata.get("chunk_id", "?") for c in chunks]

        event = log_event(
            user_id=user_id, agent="medical_rag_agent", input_summary={"query": query},
            decision=result.model_dump(), confidence=result.confidence,
            started_at=started, run_id=run_id, retrieval=retrieval_trace, **call.trace_fields(),
        )
        context_dict = result.model_dump()
        # Recorded (not LLM-generated) so guardrail_verifier can confirm the
        # retrieval filter actually scoped evidence to this user (Q13 check).
        context_dict["citation_user_ids"] = [c.metadata.get("user_id") for c in chunks]
        return {
            "medical_context": context_dict,
            "run_cost_usd": call.cost_usd,
            "run_tokens": call.total_tokens,
            "audit_log": [event],
        }
    except Exception as e:
        fault = classify_exception(e, layer=Layer.RAG)
        event = log_event(
            user_id=user_id, agent="medical_rag_agent", input_summary={"query": query},
            decision=fault.message, status="error", started_at=started, run_id=run_id, fault=fault,
        )
        return {
            "medical_context": MedicalContext(confidence=0.0, refused=True,
                                               summary="Medical Agent failed — continuing without medical context.").model_dump(),
            "errors": [{"agent": "medical_rag_agent", "fault": fault.to_dict()}],
            "guardrail_flags": ["medical_agent_failed_continuing_without_medical_context"],
            "audit_log": [event],
        }
