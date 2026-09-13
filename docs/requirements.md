# Health Sentinel — Requirements Document

**Status:** Draft v1 (for requirements grooming)
**Owner:** TBD
**Last updated:** 2026-09-13
**Source guardrails spec:** `health-sentinel-guardrails.md`

---

## 1. Purpose

Health Sentinel is a multi-agent assistant that turns a user's meals, activity,
medical documents, spending, and calendar into **safe, explainable, lifestyle-
only** nutrition and wellness guidance — never a diagnosis. The system must be
provably guardrailed: every hard stop in the guardrails spec (medical, privacy,
AI-safety, consent, technical, compliance, incident-response, monitoring,
human-oversight) is enforced in code, not just prompted for.

## 2. Goals & Non-Goals

### Goals

1. Turn a meal (photo or text) + wearable/medical/financial/calendar context
   into daily nutrition totals, SAFE-category predictions, and filtered
   recommendations.
2. Ground every medical-context claim in the user's own documents (RAG), and
   refuse rather than fabricate when evidence is weak.
3. Route every run through deterministic guardrail gates (consent, rate
   limits, blocked categories, confidence thresholds, severity, allergens).
4. Escalate to a human (nutritionist review queue) whenever confidence,
   novelty, or severity crosses a threshold.
5. Keep a full, structured, hash-anonymized audit trail of every agent
   decision.
6. Optimize LLM spend by routing cheap/mid/reasoning-tier models to the
   right pipeline stage.

### Non-Goals (current build)

- No real medical diagnosis, treatment, or medication guidance of any kind.
- No real OAuth/HealthKit/Plaid/Calendar integrations — MCP connectors are
  **simulated** with deterministic synthetic data.
- No production-grade persistence — the checkpointer, store, and rate
  limiter are all in-memory (`MemorySaver`, `InMemoryStore`, in-process
  counters), reset on process restart.
- No multi-tenant auth/session system — `user_id` is a free-text field, not
  an authenticated identity.
- No mobile client — Streamlit only.

## 3. Personas

| Persona | Role | Example needs |
|---|---|---|
| **End user** | Logs meals, connects MCPs, reads daily report | "Is my magnesium low?", "What should I eat tonight?" |
| **Nutritionist reviewer** | Human-in-the-loop approver | Approve/modify/reject flagged predictions within SLA |
| **Support / on-call** | Incident response | Investigate anomalies, guardrail breaches, model drift |
| **Data scientist** | Model/bias monitoring | Review aggregated, anonymized accuracy by cohort |

## 4. System Architecture

LangGraph `StateGraph` (chosen over Deep Agents — see `README.md` for the
full rationale: guardrails here are deterministic code gates, not
LLM-followed instructions).

```
consent_gate → rate_limit_gate → vision_agent → nutrition_agent
   → [medical_rag_agent, activity_agent, finance_agent, calendar_agent] (parallel)
   → prediction_agent → guardrail_gate
       → (if flagged) nutritionist_review [HITL interrupt] → recommendation_agent
       → (else) recommendation_agent
   → critic_agent → finalize
```

## 5. Agents & Model Routing

| # | Agent | Tier | Responsibility |
|---|---|---|---|
| 1 | vision_agent | cheap (`gpt-4o-mini`) | Meal-photo recognition |
| 2 | nutrition_agent | mid (`gpt-4o-mini`) | Macro/micro totals, 3-source cross-check |
| 3 | medical_rag_agent | mid | RAG over `data/medical_docs/*.md`, refusal on weak evidence |
| 4 | activity_agent | — | iWatch MCP (simulated) |
| 5 | finance_agent | — | Banking MCP (simulated) |
| 6 | calendar_agent | — | Calendar MCP (simulated) |
| 7 | prediction_agent | reasoning (`gpt-4o`) | SAFE-category predictions + risk dashboard |
| 8 | recommendation_agent | mid | Filtered, cited recommendations |
| — | critic_agent | reasoning | Final guardrail-checklist pass/fail |

## 6. Guardrails (enforced in `src/healthsentinel/guardrails/`)

- **Medical**: blocked-category hard stop, confidence-action table (display
  >0.80 / caution 0.60–0.80 / hide <0.60), severity escalation
  (LOW/MEDIUM/HIGH/CRITICAL), mandatory disclaimer, medical-history
  prediction weighting.
- **Hallucination**: confidence cap ≤0.92, calorie bounds 1200–3000/day,
  exercise bound ≤150 min/week, unproven-supplement/extreme-diet rejection.
- **Bias**: per-cohort accuracy variance flag (>5%), socioeconomic
  whole-food-before-supplement guard.
- **Privacy**: Tier 1/2/3 data classification, RBAC table, account masking.
- **Rate limiting**: 10 images/day, 1 analysis/day, 50 API calls/hour,
  3-sigma anomaly detection.

## 7. Human-in-the-Loop

`nutritionist_review` node pauses the graph (`langgraph.types.interrupt`,
`MemorySaver` checkpointer) when: confidence <0.60, first-week user,
severity HIGH/CRITICAL, or an upstream guardrail already blocked something.
UI resumes via `Command(resume={"type": "approve"|"modify"|"reject"})`.
SLA: CRITICAL 2h, HIGH 8h, MEDIUM/LOW 24h (tracked in code, not yet enforced
by any paging/notification system).

## 8. Shared Memory

`memory/store.py` wraps a LangGraph `Store` (currently `InMemoryStore`) for
per-user preferences, rejected recommendations, consent, and a cross-session
progress note.

## 9. RAG (medical documents)

Frontmatter + heading-aware chunking → Chroma + OpenAI embeddings → dense +
lexical-overlap fusion → refusal below a fused-score threshold (0.28).
Corpus today is 2 hand-written sample docs (`medical_history.md`,
`blood_report_latest.md`) for one demo user.

## 10. Traceability

`logging_utils.py` writes structured JSONL (`logs/audit.jsonl`): timestamp,
hashed user id, agent, redacted input, decision, confidence, severity,
latency, status. Mirrored into graph state for the UI's live trace table.

## 11. Evaluation

`eval/run_eval.py` — 11 checks: blocked-category suppression, confidence
cap, disclaimer presence, calorie bounds, rate limiting, anomaly detection,
RAG refusal-vs-answer, consent blocking, HITL triggering, end-to-end
allergen blocking. All 11 currently pass. No adversarial/red-team suite, no
regression baseline dataset, no bias-variance eval against real cohort data
yet.

## 12. Compliance

HIPAA/GDPR/CCPA/regional-law requirements are **documented** in the source
guardrails spec but **not yet implemented** as code (no encryption-at-rest
config, no data-residency logic, no formal breach-notification workflow, no
DPO/legal integration).

## 13. Settled decisions (Round 1 grooming, 2026-09-13)

1. **Scope**: portfolio/demo project for now — not on a committed production
   path. Constraint: guardrail *logic* must be written so it survives a
   later production migration unchanged (infra swaps only, no rule rewrites).
2. **Guardrail verdict authority**: a new fully deterministic guardrail
   verifier (pure Python, no LLM) becomes the authoritative pass/fail gate.
   `critic_agent` (LLM) is demoted to advisory-only — it can explain and
   flag, but can never override a deterministic-verifier failure.
3. **Guardrail thresholds/categories**: kept as fixed, spec-derived constants
   for this project stage. Added hard requirement: *no threshold ships to
   real users without clinical/nutritionist sign-off.*
4. **Adversarial/red-team evals**: required now, not deferred to a
   "production" milestone — guardrail bypass via adversarial phrasing is a
   correctness bug at any stage.
5. **RAG corpus breadth**: single-user, 2-document corpus is insufficient.
   Expand to 3-4 synthetic profiles to actually exercise personalization,
   refusal, and cross-user isolation.

## 14. Settled decisions (Round 2 grooming, 2026-09-13)

7. **`critic_agent` retained**, but narrowed to "advisory second opinion on
   already-clean runs" — see §15 Q13 for the corrected ordering vs. the
   deterministic verifier (Q6/Q7 conflict resolved there).
8. **Cross-user RAG isolation fixed now**: `retrieve()` filters Chroma by
   `user_id` metadata before the corpus expands to multiple profiles —
   closes an RBAC violation the guardrails spec itself calls out ("User: ✗
   Access other users' data").
9. **RAG corpus expands to 4 synthetic profiles**: (1) existing prediabetes +
   peanut-allergy user, (2) healthy baseline (no conditions/allergies — tests
   against over-flagging), (3) hypertension + shellfish-allergy (tests the
   sodium-flag path + a second allergen), (4) a user whose medical doc
   mentions a blocked-category family-history note (e.g. "father has a heart
   condition") — the only profile that exercises blocked-category
   suppression against real medical-RAG evidence rather than a synthetic
   prompt.
10. **Adversarial eval suite required now**, covering: (1) direct diagnosis
    requests, (2) prompt-injection to ignore guardrail instructions, (3)
    allergen smuggling via synonym/translation/misspelling, (4)
    confidence-inflation requests. Pass bar: **100% block rate** for (1) and
    (2) (hard stops, no exceptions); a lower "flagged for review counts as
    pass" bar for (3) and (4) (softer signal-quality issues, tightened
    iteratively).
11. **No abstract `Store`/`RateLimiter`/checkpointer interfaces** — explicitly
    premature for a demo-scope project (Q1); existing modules are already
    small/single-purpose enough to swap later without a speculative layer.
12. **Lightweight session identity added**: a generated UUID in
    `st.session_state`, reused per browser session, replaces raw free-text
    `user_id` for audit-trail/memory-store keys — UI-only change, no real
    auth system.

## 15. Settled decisions (Round 3 grooming, 2026-09-13)

13. **Verifier/critic ordering** (resolves the Round-2 Q6-vs-Q7 conflict):
    `recommendation_agent → guardrail_verifier → (issues found →
    nutritionist_review) / (clean → critic_agent → finalize)`. The verifier
    re-checks raw state directly (predictions, recommendations, medical
    citations) — it never needed critic's output — so this ordering keeps
    Q6's "defense in depth" intent while making Q7's "skip critic on failing
    runs" mechanically real. Verifier checklist: blocked categories,
    confidence cap, allergen presence, calorie/exercise bounds (all already
    enforced inline — this is a regression safety net, not new logic), plus
    one new check from Q8: every medical citation's source-doc `user_id`
    matches the requesting user.
14. **Re-entry routing**: state gets a `review_stage: "pre_recommendation" |
    "post_verifier"` field, set by whichever gate raises the interrupt.
    `route_after_review` uses it to send approve/modify back to
    `recommendation_agent` (pre) or `critic_agent` (post); reject always
    goes to `finalize`.

## 16. Grooming status: frontier empty

Every branch opened across Rounds 1–3 is now either settled (§13, §14, §15)
or explicitly deferred behind the Round 1 Q1 "stay demo-scope" boundary
(persistence, real MCP OAuth, full auth, incident paging, bias/vision
measurement against real data, reasoning-model benchmarking). Nothing is
left silently assumed.

## 17. Implementation status (2026-09-13)

All Round 1–3 decisions are implemented:

- `guardrails/verifier.py` — deterministic verifier, wired as
  `guardrail_verifier` node between `recommendation_agent` and
  `critic_agent`/`nutritionist_review` (§15 Q13).
- `state.review_stage` field + updated `route_after_review` (§15 Q14).
- `rag/retrieval.py` filters by `user_id`; corpus expanded to 4 profiles in
  `data/medical_docs/` (§14 Q8, Q9).
- `guardrails/medical.py` allergen matching now includes a synonym/
  translation map (peanuts↔groundnut, shellfish↔prawn, etc.).
- `eval/adversarial_cases.py` + wired into `eval/run_eval.py` — 4 adversarial
  cases at the Q10 pass bars (§14 Q10).
- `app.py` — free-text `user_id` replaced with a closed profile selector
  (synthesizes Q9's fixed corpus with Q12's "no spoofable identity" intent —
  see note below); results panel now shows the verifier (authoritative) and
  critic (advisory) side by side.

**Implementation note (small deviation from Q12 as literally worded):** Q12's
recommended answer was a generated UUID session identity. Once Q9 fixed the
corpus to 4 named profiles, a free-text field made no sense regardless of
spoofing — so `user_id` became a closed `st.selectbox` over exactly those 4
profiles instead. This satisfies Q12's actual concern (no arbitrary,
spoofable key into the audit trail / rate limiter / memory store) without
the parallel UUID identity, since a closed enum can't be spoofed either.
Flagging this explicitly rather than silently diverging from what was agreed.

`eval/run_eval.py` — **17/17 checks passing** (11 original + cross-user
isolation + deterministic-verifier-authority + 4 adversarial cases).

## 18. Settled decisions (Round 4 grooming, 2026-09-13) — historic trend reasoning

**Requirement**: reason over a user's history and observe trends, not just a
single turn — e.g. "glucose has been above range for the last 3 months,
consult a doctor" vs. "your levels look stable now."

15. **Storage**: SQLite (`data/metrics.db`, stdlib `sqlite3`), not DuckDB or a
    hosted Postgres. Rationale: every other store in this app is in-memory
    and explicitly non-durable (§2, §14 Q11); trend reasoning is the first
    feature that *requires* data to survive a process restart across weeks.
    SQLite gives real SQL over a time-windowed series with zero new infra,
    and — matching the existing `memory/store.py` / `rag/vectorstore.py`
    posture — migrating to Postgres later is a connection-string change, not
    a rewrite.
16. **Lab data source**: no manual numeric-entry field and no simulated
    lab-results MCP for this pass. Instead, the user **uploads a lab report**
    (PDF/text or photo) and an extraction agent parses it. Every extracted
    reading is checked against a fixed metric allowlist
    (`glucose_mgdl`, `weight_kg`) and physiological bounds before it is ever
    written to the store — an LLM-proposed number never reaches the database
    unvalidated.
17. **Metrics tracked in this pass**: glucose, weight, sleep. Sleep is
    captured automatically every run from the existing simulated iWatch MCP
    output (no new input needed); glucose and weight come only from an
    uploaded lab report.
18. **Verdict generation is deterministic, not LLM-reasoned**: a new
    `trends.py` module computes the trend classification (`stable` /
    `improving` / `worsening` / `insufficient_data`), a `flag_for_doctor`
    boolean, and the evidence sentence, all in plain Python (rolling
    mean/threshold-day-fraction math). `prediction_agent`'s LLM call is only
    ever handed the already-computed verdict and told to phrase it — it
    never sees the raw series and never computes a trend itself. This mirrors
    the existing `severity_from_signals` pattern exactly.
19. **Future scope (not built yet): Gmail connector.** A simulated MCP
    connector that watches a user's inbox for the latest lab-report email
    attachment and feeds it into the same extraction path automatically,
    instead of requiring a manual upload each time. Deferred behind the same
    "demo-scope, simulated MCPs only" boundary as the existing iWatch/
    banking/calendar connectors (§2) — would follow the same
    `tools/mcp_simulated.py` pattern (deterministic synthetic data, scope/
    security posture documented in the docstring, no real OAuth).

### New pipeline shape (Round 4)

```
... → nutrition_agent
   → [medical_rag_agent, activity_agent, finance_agent, calendar_agent, lab_report_agent] (parallel)
   → trend_agent (deterministic — no LLM)
   → prediction_agent → ...
```

`activity_agent` now also persists each run's `avg_sleep_hours` into the
metrics store. `lab_report_agent` extracts + validates + persists
`glucose_mgdl`/`weight_kg` from an uploaded report, when one is provided.
`trend_agent` reads the last `TREND_WINDOW_DAYS` (90) of each tracked metric
and classifies it before `prediction_agent` runs. A "Historic trends" panel
in the UI shows the same verdict/evidence independent of whether a full
analysis was run, plus a per-metric chart and a "forget my historic metrics"
deletion control (mirrors the existing RAG right-to-be-forgotten button).

`eval/unit_guardrails.py` gained deterministic checks for each trend
classifier (escalation, stable, insufficient-data paths) and a metrics-store
round-trip/delete test — all offline, no LLM or network required.

## 19. Settled decisions (Round 5 grooming, 2026-09-13)

**Requirement**: (1) move the traceability audit log out of the Streamlit UI
into a docs report + console output; (2) replace the banking connector with
an SMS connector that derives meal-timing patterns, gym-subscription
detection, and health-related messages from SMS text, with a
checkbox-based human confirmation step.

20. **Traceability relocated**: `reporting.py` renders the audit trail
    (`logging_utils.read_recent_events`) as a markdown table written to
    `docs/audit_trace_report.md` and printed to the console running the app.
    The Streamlit UI no longer shows a live audit table — the sidebar has a
    "Generate traceability report" button, and the report is also
    regenerated automatically after every graph run/HITL resume.
21. **Banking connector replaced with an SMS connector**: `finance_agent` /
    `banking_spending_summary` are removed. `tools/mcp_simulated.sms_inbox`
    returns a synthetic SMS inbox (food-delivery, gym-payment,
    health-related, and irrelevant/noise messages). `sms_parser.py`
    deterministically extracts three signal types via keyword/template
    matching — no LLM call, since this is pattern matching against known
    sender/message templates, not a reasoning task.
22. **Checkbox confirmation gate (new HITL-adjacent pattern)**: every
    extracted SMS signal is rendered as a pre-checked checkbox in the UI
    ("3c. SMS-derived signals"). Keyword matching is inherently
    approximate (e.g. "membership" could be non-gym), so the user must be
    able to rule out anything not applicable — only checked items are
    passed into `sms_confirmed` and reach `sms_agent`. This is a stronger
    validation boundary than schema validation alone, since a human
    explicitly approved each item, not just a type checker.
23. **Socioeconomic guard now dormant, documented rather than silently
    dead**: `recommendation_agent` no longer calls
    `guardrails.bias.socioeconomic_guard` — its only signal source
    (`is_budget_conscious` from the banking connector) no longer exists.
    The function itself is untouched and still unit-tested; it needs a new
    signal source (or formal removal) in a future pass. `sms_result`'s
    `has_gym_subscription` flag is passed into `recommendation_agent`'s
    prompt context instead, as informational context (not a new guardrail).
24. **Privacy classification updated**: `guardrails/privacy.py`'s
    `TIER_2_FIELDS` swaps `banking_transactions` for `sms_messages`.
25. **SMS source moved to per-profile markdown files**: `data/sms/{user_id}.md`
    (one file per UI profile, same convention as `data/medical_docs/`) holds a
    `| id | sender | time | body |` table of demo messages — food-delivery
    orders, a yoga-class payment, a gym-membership payment, and health-related
    messages (pharmacy, appointment reminders), plus OTP/promo noise so the
    parser has to discriminate. `tools/mcp_simulated.sms_inbox` reads the file
    for the four known profiles and falls back to the deterministic random
    generator for any other user_id (e.g. ad hoc eval users). Editing the demo
    data no longer requires touching code.


