# Health Sentinel

A guardrailed, multi-agent nutrition & lifestyle assistant built on **LangGraph**
(LangChain's low-level orchestration layer), with **RAG over the user's own
medical documents**, **human-in-the-loop (HITL) nutritionist review**, **shared
cross-session memory**, **multi-model cost routing**, and a full **audit
trail**. Built to satisfy every guardrail in
`health-sentinel-guardrails.md` — medical, privacy, AI-safety, consent,
technical, compliance, incident-response, monitoring, and human-oversight.

> ⚠️ This is a demo/reference implementation. MCP connectors (Google Drive,
> iWatch/HealthKit, SMS, Google Calendar) are **simulated** with
> deterministic synthetic data — no real OAuth/HealthKit/SMS-provider calls are made.

## Architecture decision: LangGraph vs. Deep Agents

Both are LangChain-ecosystem options; this workspace already has an example of
each style (`careertrajectoryoptimizer` uses **Deep Agents**, `OrgPolicyChatBot`
uses a **hand-built RAG pipeline**). Health Sentinel uses **LangGraph directly**
(not Deep Agents), for one core reason:

**Deep Agents** is built for *open-ended, LLM-planned* multi-step work: an
orchestrator LLM decides which specialist subagent to call next via a `task`
tool, and guardrails are expressed as instructions in a system prompt (e.g.
"never recommend peanuts to an allergic user"). That's an excellent fit for
the Career Trajectory Optimizer, where the workflow legitimately branches on
what the LLM decides ("does the user have a goal, or not?").

Health Sentinel's guardrails doc, by contrast, calls for **deterministic, code-
enforced hard stops**: consent gates, rate limits, blocked medical categories,
confidence-threshold gating, severity-based escalation, allergen filtering,
calorie/exercise bounds. If any of these were "an instruction the LLM should
follow" instead of "a graph edge/Python `if` the LLM cannot bypass," they would
be guardrails in name only. **LangGraph's `StateGraph`** — explicit nodes,
conditional edges, a real parallel fan-out/fan-in for the MCP agents, a
checkpointer, and `interrupt()` for HITL — lets every hard stop be enforced in
plain Python *around* the LLM calls, not inside a prompt. Deep Agents is itself
built on LangGraph, so this is "the same foundation, one layer lower" — chosen
deliberately for a health-safety system where "the agent decided to skip a
safety check" is not an acceptable failure mode.

## Multi-agent architecture

```mermaid
flowchart TD
    A[consent_gate] -->|blocked| END1[END]
    A -->|ok| B[rate_limit_gate]
    B -->|blocked| END2[END]
    B -->|ok| C[vision_agent]
    C --> D[nutrition_agent]
    D --> E[medical_rag_agent]
    D --> F[activity_agent]
    D --> G[sms_agent]
    D --> H[calendar_agent]
    E --> I[prediction_agent]
    F --> I
    G --> I
    H --> I
    I --> J[guardrail_gate]
    J -->|low confidence / new user / severity HIGH+/ blocked flag| K[nutritionist_review - HITL interrupt]
    J -->|clear| L[recommendation_agent]
    K -->|reject| N[finalize]
    K -->|approve/modify| L
    L --> M[critic_agent]
    M --> N[finalize]
    N --> END3[END]
```

| # | Agent | Model tier | Role |
|---|---|---|---|
| 1 | `vision_agent` | cheap | Meal-photo food recognition; hallucination floor (<0.50 confidence → manual entry) |
| 2 | `nutrition_agent` | mid | Macro/micro totals; simulates 3-source DB cross-check, >15% disagreement → averaged + flagged |
| 3 | `medical_rag_agent` | mid | RAG over `data/medical_docs/*.md`; refuses rather than fabricates when evidence is weak |
| 4 | `activity_agent` | — | iWatch MCP (simulated) |
| 5 | `sms_agent` | — | SMS MCP (simulated) — meal-timing patterns, gym subscription, health-related messages; user confirms/rules out each item via checkboxes before it's used |
| 6 | `calendar_agent` | — | Google Calendar MCP (simulated) — stress signal |
| 7 | `prediction_agent` | reasoning | SAFE-category-only predictions + risk dashboard; blocked-category hard stop, confidence cap 0.92, severity gating |
| 8 | `recommendation_agent` | mid | Filtered recommendations: allergen block, calorie/exercise bounds, unproven-supplement/extreme-diet rejection, budget-aware whole-food swaps |
| — | `critic_agent` | reasoning | Final guardrail-checklist review before release |

Agents 3, 4, 5, 6 run as a **real parallel fan-out/fan-in** in the graph (all
four execute concurrently after `nutrition_agent`, and `prediction_agent` waits
for all four) — matching the guardrails doc's "3 Parallel Agents" failure-
cascade section.

## Guardrails implemented (see `src/healthsentinel/guardrails/`)

- **`medical.py`** — blocked categories (hard stop), confidence-action table,
  severity escalation (LOW/MEDIUM/HIGH/CRITICAL), mandatory disclaimer,
  medical-history-based prediction weighting, allergen text scanning.
- **`hallucination.py`** — confidence cap (≤0.92), calorie bounds
  (1200–3000/day), exercise bounds (≤150 min/week), unproven-supplement /
  extreme-diet rejection, vision hallucination floor.
- **`bias.py`** — per-demographic-group accuracy variance check (>5% flags),
  socioeconomic guard (whole-food swap before paid supplements).
- **`privacy.py`** — Tier 1/2/3 data classification, RBAC permission table,
  account-number masking.
- **`rate_limit.py`** — per-user image/analysis/API-call rate limits, 3-sigma
  anomaly ("poison data") detection, physiological-validity bounds.

**Human-in-the-loop**: `nutritionist_review` node uses `langgraph.types.interrupt()`
to pause the graph (via the `MemorySaver` checkpointer) whenever: confidence
<0.60, the user is in their first week, severity is HIGH/CRITICAL, or an
upstream guardrail already blocked something. The UI resumes the graph with
`Command(resume={"type": "approve"|"modify"|"reject"})`.

**Shared memory**: `src/healthsentinel/memory/store.py` wraps LangGraph's
`InMemoryStore` (swap for `PostgresStore`/`RedisStore` in production) to
persist per-user preferences, rejected recommendations, consent, and a
cross-session progress note.

**Traceability**: `logging_utils.py` writes structured JSONL to
`logs/audit.jsonl` — timestamp, hashed user id (never raw PII), agent,
redacted input, decision, confidence, severity, latency, status — and mirrors
every event into the graph state so the UI can render a live trace table.

**Evals**: `eval/run_eval.py` is a required pre-deploy gate (mirrors
`OrgPolicyChatBot/scripts/validate_pipeline.py`) checking blocked-category
suppression, confidence capping, disclaimer presence, calorie bounds, rate
limiting, anomaly detection, RAG refusal-vs-answer behavior, consent blocking,
HITL triggering, and end-to-end allergen blocking — **11/11 passing**.

## Multi-LLM cost optimization

Configured in `.env` / `src/healthsentinel/config.py`:

| Env var | Default | Used by |
|---|---|---|
| `HEALTHSENTINEL_CHEAP_MODEL` | `gpt-4o-mini` | Vision agent (meal photo) |
| `HEALTHSENTINEL_MID_MODEL` | `gpt-4o-mini` | Nutrition, medical-RAG, recommendation agents |
| `HEALTHSENTINEL_REASONING_MODEL` | `gpt-4o` | Prediction engine + guardrail critic (highest stakes, lowest volume) |
| `HEALTHSENTINEL_EMBEDDING_MODEL` | `text-embedding-3-small` | Medical-document RAG index |

This keeps the expensive model off the hot path (thousands of meal
photos/day) and reserves it for the two calls that gate what a user actually
sees.

## RAG pipeline (medical documents)

Mirrors `OrgPolicyChatBot`'s design at a complexity level appropriate for a
per-user medical-document corpus:

1. **Ingestion** (`rag/ingestion.py`) — frontmatter/body split, then
   heading-aware section splitting, with a token-bounded recursive fallback
   for oversized sections (same shape as OrgPolicyChatBot's chunker).
2. **Indexing** (`rag/vectorstore.py`) — Chroma + OpenAI embeddings,
   persisted to `data/chroma/` (gitignored).
3. **Retrieval** (`rag/retrieval.py`) — dense similarity + lexical-overlap
   fusion, with an explicit **refusal** path (`refused=True`) when the top
   fused score is below threshold, instead of fabricating an answer.

## Setup

```bash
uv sync
cp .env.example .env   # then add your OPENAI_API_KEY (already pre-filled if you copied from another local project)
uv run python eval/run_eval.py   # guardrail + RAG + HITL eval gate — run before every change
uv run streamlit run app.py      # UI
```

## Project layout

```
healthsentinel/
  app.py                       Streamlit UI (consent, profile, meal input, HITL, audit trail)
  src/healthsentinel/
    config.py                  Multi-LLM router + paths + guardrail thresholds
    state.py                   LangGraph state schema
    graph.py                   StateGraph assembly (nodes, edges, HITL interrupt)
    schemas.py                 Pydantic structured-output schemas per agent
    logging_utils.py           JSONL audit logging (traceability)
    llm.py                     Model-tier factory
    guardrails/                medical.py, hallucination.py, bias.py, privacy.py, rate_limit.py
    memory/store.py            Cross-session shared memory (LangGraph Store)
    agents/                    vision, nutrition, medical_rag, activity, finance, calendar,
                                prediction, recommendation, critic
    rag/                       ingestion.py, vectorstore.py, retrieval.py
    tools/mcp_simulated.py     Simulated Google Drive / iWatch / SMS / Calendar MCPs
  data/
    medical_docs/              Sample user medical history + blood report (frontmatter + sections)
    grounding/nutrition_facts.md   Approved foods / safe bounds for recommendations
  eval/
    cases.py, run_eval.py      Guardrail evaluation harness (required gate)
  logs/audit.jsonl             Append-only structured audit trail (gitignored)
```
