"""Generates the "Team Breakout Handout" submission PDF for The Gen Academy's
Mastering Agentic AI — Evals Week Breakout, filled in for the Health Sentinel
project team.

Mirrors the reference handout's exact structure (numbered sections, team
table, icebreaker, Q1/Q2/Q3, project write-up, next step) rather than the
marketing design system used by generate_project_pdfs.py — this is a form
to submit, not a flyer.

Run:
    uv run python docs/generate_breakout_handout.py
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
HTML_DIR = DOCS_DIR / "html"
PDF_DIR = DOCS_DIR / "pdfs"
HTML_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]

# --- fields the user supplied ------------------------------------------------
TEAM_MEMBERS = [
    ("Gnana Sudheer Gavarraju", "sudheeronsocial@gmail.com"),
]
POINT_PERSON = "Gnana Sudheer Gavarraju"
ICEBREAKER_NAME = "Sudheer"
ICEBREAKER_LOCATION = "Vijayawada"
ICEBREAKER_TASK = "Summarizing my emails and tracking/planning my monthly spend"
MEETING_CADENCE = "Not yet scheduled (TBD)"

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: #1B2430; font-size: 9.6pt; line-height: 1.42;
  margin: 0; padding: 0;
}
.masthead { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #131C28; padding-bottom: 2.4mm; margin-bottom: 4mm; }
.masthead .org { font-size: 8pt; font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase; color: #33475A; }
.masthead .org b { color: #131C28; }
h1 { font-size: 17pt; font-weight: 800; margin: 0 0 1mm 0; color: #131C28; }
.deadline { font-size: 8.6pt; color: #BE123C; font-weight: 700; margin-bottom: 2.4mm; }
.intro { font-size: 8.8pt; color: #33475A; margin-bottom: 1.6mm; }
.submit-link { font-size: 8.4pt; color: #1E3A8A; margin-bottom: 5mm; word-break: break-all; }

.section { margin-top: 6mm; }
.section-head { display: flex; align-items: center; gap: 2.6mm; margin-bottom: 2.4mm; }
.badge { width: 6.4mm; height: 6.4mm; border-radius: 50%; background: #1E3A8A; color: #fff; font-weight: 800; font-size: 9pt; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.section-title { font-size: 11.5pt; font-weight: 800; color: #131C28; }
.section-desc { font-size: 8.4pt; color: #62788C; margin: 0 0 2.4mm 8.8mm; line-height: 1.4; }

table.team { width: 100%; border-collapse: collapse; margin-left: 8.8mm; width: calc(100% - 8.8mm); }
table.team th { text-align: left; font-size: 7.6pt; text-transform: uppercase; letter-spacing: 0.4px; color: #62788C; padding: 1.6mm 2.4mm; border-bottom: 1.4px solid #D6E0E8; background: #EEF3F6; }
table.team td { padding: 1.8mm 2.4mm; border-bottom: 1px solid #EEF3F6; font-size: 8.6pt; color: #33475A; }
table.team td.n { color: #93A5B5; width: 6%; }
.point-person { margin: 2.4mm 0 0 8.8mm; font-size: 8.6pt; }
.point-person b { color: #131C28; }

.qa-block { margin: 0 0 3mm 8.8mm; }
.qa-q { font-size: 8.8pt; font-weight: 700; color: #131C28; margin-bottom: 0.8mm; }
.qa-a { font-size: 8.6pt; color: #33475A; background: #F5F7FA; border-left: 2.6px solid #1E3A8A; padding: 1.8mm 3mm; border-radius: 1.6mm; }

.icebreaker-card { margin-left: 8.8mm; background: #F5F7FA; border-left: 2.6px solid #B45309; border-radius: 1.6mm; padding: 2mm 3.4mm; font-size: 8.6pt; }
.icebreaker-card b { color: #131C28; }

ul.proj { margin: 0 0 0 8.8mm; padding-left: 4mm; }
ul.proj li { font-size: 8.6pt; color: #33475A; margin-bottom: 1.6mm; line-height: 1.42; }
ul.proj li b { color: #131C28; }

.next-step { margin: 5mm 0 0 8.8mm; background: #EDE6FB; border-left: 2.6px solid #6D28D9; border-radius: 1.6mm; padding: 2mm 3.4mm; font-size: 8.6pt; }
.next-step b { color: #131C28; }


.scope-strip { margin: 5mm 0 0 8.8mm; border: 1px solid #D6E0E8; border-radius: 1.6mm; background: #EEF3F6; padding: 2mm 3.4mm; font-size: 8pt; color: #33475A; line-height: 1.5; }
.scope-strip b { color: #131C28; }
.scope-strip .sep { color: #93A5B5; padding: 0 1.2mm; }
.resubmit { margin: 3.4mm 0 0 8.8mm; font-size: 8.4pt; color: #33475A; }
.resubmit a, .resubmit span.url { color: #1E3A8A; word-break: break-all; }
.footer { margin-top: 8mm; text-align: center; font-size: 7.2pt; color: #93A5B5; border-top: 1px solid #D6E0E8; padding-top: 2mm; }
"""


def build_html() -> str:
    team_rows = ""
    for i in range(7):
        if i < len(TEAM_MEMBERS):
            name, email = TEAM_MEMBERS[i]
        else:
            name, email = "&mdash;", "&mdash;"
        team_rows += f'<tr><td class="n">{i + 1}</td><td>{name}</td><td>{email}</td></tr>\n'

    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><style>{CSS}</style></head>
<body>

<div class="masthead">
  <div class="org"><b>The Gen Academy</b> &middot; Mastering Agentic AI &middot; Evals Week Breakout</div>
</div>

<h1>Team Breakout Handout</h1>
<div class="deadline">Deadline to submit: 12th Sept 11:59pm PT</div>
<div class="intro">Meet your team, pick one use case, and sketch an end to end AI agent design.</div>
<div class="submit-link">Submission form: https://forms.gle/E6cKoFUJxV5g86EC7</div>

<div class="section">
  <div class="section-head"><div class="badge">1</div><div class="section-title">Who is on this team</div></div>
  <div class="section-desc">Add everyone&rsquo;s full name and email. Leave the last rows for members who join your team later.</div>
  <table class="team">
    <tr><th>#</th><th>Full name</th><th>Email</th></tr>
    {team_rows}
  </table>
  <div class="point-person">Point person (owns this doc and coordinates the team): <b>{POINT_PERSON}</b></div>
</div>

<div class="section">
  <div class="section-head"><div class="badge">2</div><div class="section-title">Warm up: go around the room</div></div>
  <div class="section-desc">Icebreaker. Tell us your name, where you are joining from, and the one boring or repetitive task you would happily hand off to an AI agent tomorrow if you could.</div>
  <div class="icebreaker-card">
    <b>{ICEBREAKER_NAME}</b>, joining from <b>{ICEBREAKER_LOCATION}</b> &mdash; would happily hand off:
    &ldquo;{ICEBREAKER_TASK}&rdquo; to an AI agent.
  </div>
</div>

<div class="section">
  <div class="section-head"><div class="badge">3</div><div class="section-title">Pick a topic and sketch the design</div></div>
  <div class="section-desc">Talk through these three questions together, then jot your thinking below.</div>

  <div class="qa-block">
    <div class="qa-q">Q1. Pick the use case.</div>
    <div class="qa-a">
      Health Sentinel &mdash; a guardrailed multi-agent nutrition &amp; lifestyle assistant. Turning meals,
      wearable data, medical documents, and everyday spending/SMS signals into safe, explainable health
      guidance is slow and error-prone today: people either get a generic chatbot that will happily invent a
      confident-sounding medical claim, or no synthesis at all across scattered sources (a fitness app, a lab
      report PDF, a bank statement, a calendar). The team found this compelling specifically because the
      failure mode (a confidently wrong "you're fine" or a fabricated diagnosis) is genuinely high-stakes, which
      makes it a strong test of guardrails and evals &mdash; not just a demo of agent orchestration.
    </div>
  </div>

  <div class="qa-block">
    <div class="qa-q">Q2. Knowledge and tools.</div>
    <div class="qa-a">
      <b>Knows (RAG):</b> the user's own medical documents (blood reports, medical history) are chunked,
      embedded, and retrieved per-user with a fused dense + lexical score; the agent refuses rather than
      answers when retrieval evidence is weak, instead of fabricating a medical fact.
      <br/><b>Does (tools/actions):</b> simulated MCP connectors stand in for real integrations &mdash; an
      iWatch-style connector for sleep/activity, an SMS connector that parses order/gym/health messages
      (user-confirmed via checkboxes before use), a calendar connector for a stress signal, and a lab-report
      upload path that extracts glucose/weight readings into a small SQLite time series for trend reasoning.
    </div>
  </div>

  <div class="qa-block">
    <div class="qa-q">Q3. Autonomy and evals.</div>
    <div class="qa-a">
      <b>Autonomy vs. workflow:</b> mostly a fixed workflow, deliberately. The graph topology (consent &rarr;
      rate limit &rarr; meal/context agents &rarr; prediction &rarr; guardrail gate &rarr; optional human review
      &rarr; recommendation &rarr; deterministic verifier &rarr; advisory critic &rarr; finalize) is hard-coded;
      the LLM is free to reason only inside narrow, schema-validated steps (what to predict, how to phrase a
      recommendation), never over whether a safety gate applies. A deterministic, pure-Python verifier is the
      authoritative pass/fail check; an LLM critic is advisory-only and can never override it.
      <br/><b>Evals:</b> a two-tier eval suite &mdash; 40+ deterministic offline checks (guardrail thresholds,
      allergen matching, trend classification, category allowlist) that need no LLM call and gate CI on every
      push, plus a full end-to-end suite (RAG refusal/answer, human-in-the-loop triggering, cross-user
      isolation) and an adversarial red-team suite (direct diagnosis requests, prompt injection, allergen
      smuggling, confidence inflation) with a 100% block-rate bar on the hard cases. 59/59 checks pass today.
    </div>
  </div>
</div>

<div class="section">
  <div class="section-head"><div class="badge">4</div><div class="section-title">Our project</div></div>
  <div class="section-desc">Use case, where RAG fits, tools the agent calls, autonomy vs workflow, and how you would evaluate it.</div>
  <ul class="proj">
    <li><b>Use case:</b> Health Sentinel &mdash; guardrailed nutrition &amp; lifestyle coaching that never diagnoses, built as a LangGraph StateGraph rather than a free-form agent loop.</li>
    <li><b>Where RAG fits:</b> the user's own medical documents only, retrieved with a per-user metadata filter and a hard refusal threshold &mdash; grounding, not general medical knowledge.</li>
    <li><b>Tools the agent calls:</b> simulated wearable (iWatch), SMS, calendar, and lab-report-upload connectors; every SMS-derived signal is confirmed by the user via checkboxes before it's used.</li>
    <li><b>Autonomy vs. workflow:</b> fixed graph topology with deterministic gates; the LLM proposes, code (allowlists, bounds checks, the authoritative verifier) disposes.</li>
    <li><b>How we'd evaluate it:</b> deterministic unit evals for every guardrail + an adversarial red-team suite with a hard 100% block-rate bar for diagnosis/prompt-injection attempts, gating CI before any change ships.</li>
  </ul>
</div>

<div class="next-step">
  <b>Next step.</b> How and when we'll meet over the next 3 weeks: {MEETING_CADENCE}.
</div>

<div class="resubmit">Please submit your projects here: <span class="url">https://forms.gle/E6cKoFUJxV5g86EC7</span></div>

<div class="scope-strip">
  <b>In scope:</b> RAG, tool calling, autonomy vs workflow, evals.<span class="sep">&middot;</span>
  <b>Not required:</b> fine tuning, AI security.<span class="sep">&middot;</span>
  <b>Build over 3 weeks</b> (optional).<span class="sep">&middot;</span>
  <b>Demo day</b> July 12 to 13.
</div>

<div class="footer">The Gen Academy &middot; Mastering Agentic AI &middot; Evals Week Breakout &middot; Team Breakout Handout</div>

</body></html>"""


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("No Chrome/Chromium binary found for HTML->PDF conversion.")


def main() -> None:
    chrome_bin = find_chrome()
    html_path = HTML_DIR / "06_team_breakout_handout.html"
    pdf_path = PDF_DIR / "06_team_breakout_handout.pdf"
    html_path.write_text(build_html(), encoding="utf-8")
    subprocess.run(
        [
            chrome_bin, "--headless", "--disable-gpu",
            "--no-pdf-header-footer", "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}", str(html_path),
        ],
        check=True, capture_output=True,
    )
    print(f"- {pdf_path.relative_to(DOCS_DIR.parent)}")


if __name__ == "__main__":
    main()
