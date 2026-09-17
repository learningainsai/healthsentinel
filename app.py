"""Streamlit UI for Health Sentinel — a guardrailed multi-agent health &
nutrition assistant (LangGraph orchestration, RAG over medical documents,
HITL nutritionist review, shared cross-session memory, full audit trail).

Run with:
    uv run streamlit run app.py
"""
from __future__ import annotations

import base64
import os
import sys
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

load_dotenv(PROJECT_ROOT / ".env")

from healthsentinel import config as hs_config  # noqa: E402
from healthsentinel import metrics_store, reporting, staging  # noqa: E402
from healthsentinel.allergy_normalization import normalize_free_text_term  # noqa: E402
from healthsentinel.graph import GLOBAL_STORE, build_graph  # noqa: E402
from healthsentinel.guardrails.medical import KNOWN_ALLERGY_CATEGORIES, MEDICAL_DISCLAIMER  # noqa: E402
from healthsentinel.memory import store as mem  # noqa: E402
from healthsentinel.rag.vectorstore import build_index, delete_user_documents  # noqa: E402
from healthsentinel.sms_parser import parse_sms_messages  # noqa: E402
from healthsentinel.tools.mcp_simulated import sms_inbox  # noqa: E402
from healthsentinel.trends import classify_all  # noqa: E402

st.set_page_config(page_title="Health Sentinel", page_icon="\U0001FA7A", layout="wide")
st.title("Health Sentinel")
st.caption("Guardrailed multi-agent nutrition & lifestyle assistant — LangGraph orchestration, RAG, HITL, full audit trail")


def _strip_links(md: str) -> str:
    """Neutralize model-authored links/images before rendering (review §7):
    keep the visible text, drop the target URL so nothing is clickable."""
    import re

    md = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", md)   # images -> alt text
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)     # links -> link text
    return md

has_openai = hs_config.is_real_key(os.environ.get("OPENAI_API_KEY"))

# --- sidebar -----------------------------------------------------------------
with st.sidebar:
    st.header("Setup")
    key_input = st.text_input("OPENAI_API_KEY", type="password", placeholder="sk-...")
    if key_input.strip():
        os.environ["OPENAI_API_KEY"] = key_input.strip()
        has_openai = True
    st.write("OPENAI_API_KEY:", "\u2705 found" if has_openai else "\u274c not set")

    st.divider()
    st.subheader("Multi-LLM cost routing")
    st.caption("Different pipeline stages use different model tiers to balance cost vs. stakes.")
    st.table({
        "stage": ["Vision (meal photo)", "Nutrition / MCP agents / Recs", "Prediction engine + Critic"],
        "model": [hs_config.MODELS.cheap, hs_config.MODELS.mid, hs_config.MODELS.reasoning],
    })

    st.divider()
    st.subheader("Medical document RAG index")
    if st.button("(Re)build medical RAG index"):
        with st.spinner("Chunking + embedding data/medical_docs/*.md ..."):
            n = build_index(force=True)
        st.success(f"Indexed {n} chunks from data/medical_docs/.")

    st.divider()
    st.subheader("Traceability report")
    st.caption(
        "The audit trail is not shown as a live table in this UI — it's written "
        "to a markdown report under docs/ and printed to the console running this app."
    )
    if st.button("Generate traceability report"):
        path = reporting.write_report()
        reporting.print_report()
        st.success(f"Report written to {path} and printed to the console.")

    st.divider()
    if st.button("New session (new thread)"):
        for k in ("thread_id", "result", "interrupt_payload"):
            st.session_state.pop(k, None)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"hs-{uuid.uuid4().hex[:8]}"

graph = build_graph()
config = {"configurable": {"thread_id": st.session_state.thread_id}}

# --- consent gates (guardrails doc §4 — granular, explicit) -----------------
st.subheader("1. Consent (required before anything runs)")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Tier 1 — Core function (required)**")
    consent_image = st.checkbox("Allow meal image / text processing (Vision + Nutrition agents)")
    consent_not_medical = st.checkbox("I understand this is NOT medical advice")
    st.markdown("**Tier 2 — Data integration (optional, simulated MCPs)**")
    consent_medical_docs = st.checkbox("Connect medical documents (Google Drive MCP, simulated)", value=True)
    consent_iwatch = st.checkbox("Connect activity tracker (iWatch MCP, simulated)", value=True)
with c2:
    st.markdown("**Tier 3 — Analytics (optional)**")
    consent_analytics = st.checkbox("Share anonymized aggregates for model improvement")
    st.markdown("**Tier 4 — Notifications (optional)**")
    consent_notify = st.checkbox("Critical alerts (immediate)", value=True)
    st.markdown("**Data connectors**")
    consent_sms = st.checkbox(
        "Connect SMS access (simulated — parses order/gym/health SMS for pattern detection)", value=True,
    )
    consent_calendar = st.checkbox("Connect calendar (Google Calendar MCP, simulated — for stress signal)", value=True)

tier1_ok = consent_image and consent_not_medical

# --- profile ------------------------------------------------------------------
# A closed set of seeded profiles instead of free text: this is the demo
# corpus's identity space (RAG docs are keyed to these exact user_ids) and it
# also closes the "arbitrary, spoofable user_id" gap a free-text field would
# leave in the audit trail / rate limiter / memory store.
PROFILES = {
    "demo-user": {"label": "Demo user — prediabetes + peanut allergy", "conditions": ["prediabetes"], "allergies": ["peanuts"]},
    "healthy-baseline-user": {"label": "Healthy baseline — no conditions/allergies", "conditions": [], "allergies": []},
    "hypertension-user": {"label": "Hypertension + shellfish allergy", "conditions": ["hypertension"], "allergies": ["shellfish"]},
    "family-history-user": {"label": "Family history of heart condition (patient is healthy)", "conditions": [], "allergies": []},
}

st.subheader("2. Profile")
p1, p2, p3 = st.columns(3)
with p1:
    user_id = st.selectbox("Profile", list(PROFILES.keys()), format_func=lambda u: PROFILES[u]["label"])
    is_new_user = st.checkbox("This is a new user (first week — all predictions reviewed)")
with p2:
    conditions = st.multiselect("Known conditions", ["prediabetes", "hypertension"], default=PROFILES[user_id]["conditions"])
with p3:
    allergies = st.multiselect("Allergies", ["peanuts", "shellfish", "soy", "gluten", "dairy"], default=PROFILES[user_id]["allergies"])
free_text_allergy = st.text_input(
    "Other allergy/condition not listed above (optional, free text)",
    placeholder="e.g. prawns, groundnuts...",
    help="Normalized to a known category by an LLM when you run the analysis — the raw term you type "
         "is always also checked literally, even if normalization fails or is unsure.",
)

with st.expander("Data controls (privacy)"):
    st.caption("Right-to-be-forgotten: remove this profile's medical document chunks and historic metrics.")
    dc1, dc2 = st.columns(2)
    if dc1.button("Forget my medical documents (revoke)"):
        removed = delete_user_documents(user_id)
        st.success(f"Removed {removed} indexed chunk(s) for '{user_id}'. Rebuild the index to restore.")
    if dc2.button("Forget my historic metrics (glucose/weight/sleep)"):
        removed = metrics_store.delete_user_metrics(user_id)
        st.success(f"Removed {removed} historic reading(s) for '{user_id}'.")

# --- day-end intake queue ------------------------------------------------------
# No cron/scheduler: the user stages documents/notes at their own pace during
# the day, then presses "Run day-end analysis" whenever they want — a manual
# trigger, not a scheduled job. The queue is disk-persisted (staging.py) so it
# survives a page refresh, and intake_agent (LangGraph node) classifies/routes
# everything staged into the existing per-agent input fields on the next run.
st.subheader("3. Today's documents & notes")
CATEGORY_LABELS = {
    "meal": "Meal", "health_report": "Health report", "activity": "Activity report",
    "lab": "Lab report", "sms": "SMS report", "calendar": "Calendar",
}
dc1, dc2 = st.columns([1, 2])
with dc1:
    category = st.selectbox("Document category", list(CATEGORY_LABELS.keys()), format_func=lambda k: CATEGORY_LABELS[k])
    attach_file = st.file_uploader(
        "Attach a file", type=["pdf", "txt", "md", "png", "jpg", "jpeg"], key="staging_attach_uploader",
    )
    if st.button("➕ Add to today's queue", disabled=attach_file is None):
        staging.add_attachment(
            user_id, category, attach_file.name,
            base64.b64encode(attach_file.getvalue()).decode(),
            attach_file.type or "application/octet-stream",
        )
        st.rerun()
with dc2:
    note_text = st.text_area(
        "Or describe anything in plain text",
        placeholder="e.g. 'grilled chicken and rice for lunch, ran 5k this morning, glucose reading was 140'",
        key="staging_note_text",
    )
    st.caption(
        "A classifier agent reads this at run time and routes each part to the right pipeline "
        "agent (meal, activity, lab, medical, SMS, calendar) — no need to pick a category."
    )
    if st.button("➕ Add note to today's queue", disabled=not note_text.strip()):
        staging.add_note(user_id, note_text.strip())
        st.rerun()

staged_items = staging.list_items(user_id)
if staged_items:
    st.caption(f"Staged so far today ({len(staged_items)}) — cleared automatically after a successful run:")
    for item in staged_items:
        row1, row2 = st.columns([6, 1])
        if item["kind"] == "attachment":
            row1.write(f"📎 **{CATEGORY_LABELS.get(item['category'], item['category'])}** — {item['filename']}")
        else:
            row1.write(f"📝 {item['text'][:120]}{'...' if len(item['text']) > 120 else ''}")
        if row2.button("🗑", key=f"remove_staged_{item['id']}"):
            staging.remove_item(user_id, item["id"])
            st.rerun()
else:
    st.caption("Nothing staged yet today — add a document or note above.")

st.subheader("4. Simulated SMS signals (optional)")
st.caption(
    "Simulated SMS connector: detects meal-timing patterns from food-delivery texts, "
    "gym-subscription payments, and other health-related messages. Review the checkboxes "
    "below and uncheck anything that doesn't apply — only checked items are used in the analysis. "
    "(Separate from the 'SMS report' document category above, which is for a manually attached file.)"
)
sms_confirmed: dict[str, list] = {"meal_timing": [], "gym_subscription": [], "health_related": []}
if consent_sms:
    sms_parsed = parse_sms_messages(sms_inbox(user_id))

    def _render_sms_group(label: str, items: list[dict]) -> list[dict]:
        if not items:
            st.caption(f"No {label.lower()} detected in the simulated SMS inbox.")
            return []
        st.markdown(f"**{label}**")
        confirmed_items = []
        for item in items:
            checked = st.checkbox(item["snippet"], value=True, key=f"sms_{item['type']}_{item['id']}")
            if checked:
                confirmed_items.append(item)
        return confirmed_items

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        sms_confirmed["meal_timing"] = _render_sms_group("Meal-timing patterns", sms_parsed["meal_timing"])
    with sc2:
        sms_confirmed["gym_subscription"] = _render_sms_group("Gym subscription", sms_parsed["gym_subscription"])
    with sc3:
        sms_confirmed["health_related"] = _render_sms_group("Health-related messages", sms_parsed["health_related"])
else:
    st.caption("SMS connector disabled — enable 'Connect SMS access' above to detect patterns.")

run_clicked = st.button("Run day-end analysis", type="primary", disabled=not (tier1_ok and staged_items))
if not tier1_ok:
    st.info("Both Tier 1 checkboxes are required before you can run an analysis.")
elif not staged_items:
    st.info("Stage at least one document or note above before running.")

if run_clicked:
    if not has_openai:
        st.error("OPENAI_API_KEY is required. Add it in the sidebar.")
    else:
        run_id_for_normalization = st.session_state.thread_id
        effective_allergies = list(allergies)
        if free_text_allergy.strip():
            extra_terms = normalize_free_text_term(
                free_text_allergy, KNOWN_ALLERGY_CATEGORIES, run_id=run_id_for_normalization,
            )
            for term in extra_terms:
                if term not in effective_allergies:
                    effective_allergies.append(term)
            if len(extra_terms) > 1:
                st.caption(f"Mapped '{free_text_allergy}' → also checking as '{extra_terms[1]}'.")
            else:
                st.caption(f"Could not confidently map '{free_text_allergy}' to a known category — checking it literally.")
        initial_state = {
            "user_id": user_id,
            "consent": {
                "tier1_core": tier1_ok,
                "tier2_medical_docs": consent_medical_docs,
                "tier2_iwatch": consent_iwatch,
                "tier2_sms": consent_sms,
                "tier2_calendar": consent_calendar,
                "tier3_analytics": consent_analytics,
                "tier4_notifications": consent_notify,
            },
            "profile": {"is_new_user": is_new_user, "conditions": conditions, "allergies": effective_allergies},
            "staged_attachments": [i for i in staged_items if i["kind"] == "attachment"],
            "staged_notes": [i["text"] for i in staged_items if i["kind"] == "note"],
            "sms_confirmed": sms_confirmed,
        }
        with st.status("Running Health Sentinel pipeline...", expanded=True) as status:
            try:
                status.update(label="Consent + rate-limit gates...")
                result = graph.invoke(initial_state, config=config)
                if result.get("__interrupt__"):
                    status.update(label="Paused — human review required", state="complete")
                else:
                    status.update(label="Analysis complete", state="complete")
                st.session_state.result = result
                # Raw staged documents/notes are consumed by intake_agent above
                # (already checkpointed into the graph run) — only the values
                # they produced need to persist (metrics_store / RAG index).
                staging.clear(user_id)
                reporting.write_report()
                reporting.print_report()
            except Exception as e:
                status.update(label="Run failed", state="error")
                st.error(f"{type(e).__name__}: {e}")

# --- results -------------------------------------------------------------------
result = st.session_state.get("result")
if result:
    st.divider()

    if result.get("blocked"):
        st.error(f"Blocked: {result.get('block_reason')}")

    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        kind = payload.get("kind", "nutritionist_review")

        if kind == "human_edit":
            st.subheader(f"\U0001F4DD Review required: {payload.get('label', payload.get('stage'))}")
            st.caption(
                "Every LLM stage output must be reviewed (and may be edited) before it moves on to the "
                "next stage or is stored in the final report. Edits are re-checked for prompt-injection "
                "patterns before they're accepted."
            )
            if payload.get("error"):
                st.error(f"Your last edit was rejected: {payload['error']}. Please revise and try again.")
            edited_text = st.text_area(
                "Editable output", value=payload.get("content", ""), height=200, key=f"edit_{payload.get('stage')}",
            )
            if st.button("\u2705 Confirm & Continue"):
                with st.spinner("Validating and resuming pipeline..."):
                    st.session_state.result = graph.invoke(
                        Command(resume={"edited_text": edited_text}), config=config,
                    )
                reporting.write_report()
                reporting.print_report()
                st.rerun()
        else:
            st.subheader("\U0001F9D1\u200D\u2695\uFE0F Human-in-the-loop: Nutritionist review required")
            st.warning(f"Severity: **{payload.get('severity')}** — SLA: review within {payload.get('sla_hours')}h")
            st.write("Reasons:", payload.get("review_reasons"))
            st.json(payload.get("prediction_result"))

            col1, col2, col3 = st.columns(3)
            decision = None
            if col1.button("\u2705 Approve"):
                decision = {"type": "approve"}
            if col2.button("\u270F\uFE0F Modify (send back for coaching-agent revision)"):
                decision = {"type": "modify"}
            if col3.button("\u274C Reject"):
                decision = {"type": "reject"}
            if decision:
                with st.spinner("Resuming pipeline..."):
                    st.session_state.result = graph.invoke(Command(resume=decision), config=config)
                reporting.write_report()
                reporting.print_report()
                st.rerun()
    else:
        predictions = (result.get("prediction_result") or {}).get("predictions", [])
        risk = (result.get("prediction_result") or {}).get("risk_dashboard")
        recs = (result.get("recommendation_result") or {}).get("recommendations", [])
        medical_ctx = result.get("medical_context") or {}
        critic = result.get("critic_review") or {}

        left, right = st.columns([2, 1])
        with left:
            st.subheader("Final report")
            st.markdown(_strip_links(result.get("final_report", "(no report)")))

            if recs:
                st.caption("Reject a suggestion to stop seeing it (and close semantic rephrasings of it) in future runs:")
                for i, r in enumerate(recs):
                    rej_col, label_col = st.columns([1, 5])
                    if rej_col.button("\U0001F6AB", key=f"reject_rec_{i}_{r['title']}", help="Reject this suggestion"):
                        mem.reject_recommendation(GLOBAL_STORE, user_id, r["title"])
                        st.success(f"Rejected '{r['title']}' — it (and close rephrasings) will be suppressed going forward.")
                    label_col.caption(r["title"])

        with right:
            run_status = result.get("run_status", "success")
            st.subheader("Run status")
            if run_status == "success":
                st.success("success")
            else:
                st.warning(f"{run_status} — recovered faults: {result.get('recovered_faults', 0)}")
            st.caption(
                f"Cost: ${result.get('run_cost_usd', 0.0):.4f} · "
                f"Tokens: {result.get('run_tokens', 0)} · "
                f"Run ID: {result.get('run_id', '?')}"
            )
            if risk:
                st.subheader("Risk dashboard")
                st.metric("Overall risk score", f"{risk.get('overall_score', 0):.2f}")
                st.write({
                    "Glucose trend": risk.get("glucose_trend_risk"),
                    "Magnesium deficiency": risk.get("magnesium_deficiency_risk"),
                    "Sleep deprivation": risk.get("sleep_deprivation_risk"),
                    "Stress": risk.get("stress_risk"),
                })
            st.subheader("Severity")
            st.write(result.get("severity", "LOW"))
            if medical_ctx.get("refused"):
                st.warning("Medical-document RAG had insufficient evidence — continued without it.")
            elif medical_ctx.get("citations"):
                st.caption("Medical context citations:")
                for c in medical_ctx["citations"]:
                    st.caption(f"- {c}")

        st.divider()
        verifier_col, critic_col = st.columns(2)
        with verifier_col:
            st.subheader("Deterministic guardrail verifier (authoritative)")
            verifier_passed = result.get("verifier_passed")
            v_badge = "\u2705 PASSED" if verifier_passed else "\u274c FAILED"
            st.write(f"{v_badge} — this is a pure-Python re-check; it gates release, never the LLM critic.")
            for issue in result.get("verifier_issues", []):
                st.write(f"- {issue}")
        with critic_col:
            st.subheader("LLM critic (advisory only)")
            if critic:
                badge = "\u2705 PASSED" if critic.get("passed") else "\u26A0\uFE0F ISSUES FOUND"
                st.write(f"{badge} — guardrail score {critic.get('guardrail_score', 0):.0%}")
                if critic.get("issues"):
                    for issue in critic["issues"]:
                        st.write(f"- {issue}")
            else:
                st.caption("Critic did not run this turn (only runs when the deterministic verifier is clean).")

    flags = result.get("guardrail_flags", [])
    if flags:
        with st.expander(f"Guardrail flags raised this run ({len(flags)})"):
            for f in flags:
                st.write(f"- {f}")

    errors = result.get("errors", [])
    if errors:
        with st.expander(f"Agent errors this run ({len(errors)}) — graceful degradation applied"):
            for err in errors:
                fault = err.get("fault", {})
                st.write(f"- **{err['agent']}** [{fault.get('fault_class', 'unknown')}]: {fault.get('message', err.get('error', '?'))}")

    lab_report_result = result.get("lab_report_result") or {}
    if lab_report_result.get("accepted") or lab_report_result.get("rejected"):
        with st.expander("Lab report extraction this run"):
            if lab_report_result.get("accepted"):
                st.write("Accepted readings:", lab_report_result["accepted"])
            if lab_report_result.get("rejected"):
                st.write("Rejected (failed allowlist/bounds check):", lab_report_result["rejected"])

# --- historic trends ---------------------------------------------------------------
st.divider()
st.subheader("4. Historic trends (glucose / weight / sleep)")
st.caption(
    f"Deterministic classification over the trailing {hs_config.TREND_WINDOW_DAYS} days per metric — "
    "the verdict and evidence text are computed in code; only the phrasing in the final report comes from an LLM."
)
trend_series = {
    metric: metrics_store.get_series(user_id, metric, window_days=hs_config.TREND_WINDOW_DAYS)
    for metric in (hs_config.ALLOWED_LAB_METRICS | {"sleep_hours"})
}
trend_verdicts = classify_all(trend_series)
t1, t2, t3 = st.columns(3)
for col, metric_name, label in zip((t1, t2, t3), ("glucose_mgdl", "weight_kg", "sleep_hours"),
                                    ("Glucose (mg/dL)", "Weight (kg)", "Sleep (hours)")):
    with col:
        st.markdown(f"**{label}**")
        verdict = trend_verdicts.get(metric_name, {})
        readings = trend_series.get(metric_name, [])
        if readings:
            st.line_chart({label: [r.value for r in readings]})
        badge = {"stable": "\u2705", "improving": "\U0001F7E2", "worsening": "\u26A0\uFE0F",
                 "insufficient_data": "\u2139\uFE0F"}.get(verdict.get("verdict"), "")
        st.write(f"{badge} {verdict.get('verdict', 'insufficient_data')}")
        st.caption(verdict.get("evidence", ""))

# --- shared memory ---------------------------------------------------------------
st.divider()
st.subheader("5. Shared cross-session memory")
if st.button("Recall last progress note for this user"):
    note = mem.get_progress_note(GLOBAL_STORE, user_id)
    st.info(note or "No progress note saved yet for this user.")

st.divider()
st.caption(
    f"Traceability: the audit trail is written to `{reporting.REPORT_PATH.relative_to(hs_config.PATHS.project_root)}` "
    "and printed to the console after every run — use 'Generate traceability report' in the sidebar to refresh on demand."
)


st.divider()
with st.expander("Mandatory disclaimer"):
    st.text(MEDICAL_DISCLAIMER)
