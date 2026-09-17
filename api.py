"""Small HTTP API for the Angular client.

Run with:
    uv run uvicorn api:app --reload --port 8000

The browser never receives the OpenAI key; all model calls stay in the
existing instrumented, structured-output LLM boundary.
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from healthsentinel.guardrails.prompt_injection import assert_safe_for_llm  # noqa: E402
from healthsentinel.ask_graph import run_ask_flow  # noqa: E402
from healthsentinel.schemas import AskAnalysis  # noqa: E402


class AskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    user_id: str = Field(default="demo-user", min_length=1, max_length=100)


class AskResponse(BaseModel):
    category: Literal[
        "symptom", "sleep", "nutrition", "lab", "stress", "activity", "medication", "other"
    ]
    needs_more_details: bool
    reason: str
    prompt_version: str
    analysis: AskAnalysis | None = None


app = FastAPI(title="Health Sentinel API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4300"],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ask/classify", response_model=AskResponse)
def classify_ask_prompt(request: AskRequest) -> AskResponse:
    safe, issues, clean_text = assert_safe_for_llm(request.prompt)
    if not safe:
        raise HTTPException(status_code=400, detail={"issues": issues})

    try:
        result = run_ask_flow(user_id=request.user_id, prompt=clean_text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The Ask Sentinel model is temporarily unavailable") from exc

    analysis = result.get("analysis")
    return AskResponse(
        category=result.get("category", "other"),
        needs_more_details=result.get("needs_more_details", True),
        reason=result.get("classification_reason", "More detail is needed."),
        prompt_version="2026-09-17.1",
        analysis=analysis,
    )
