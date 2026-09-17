"""Generate the Health Sentinel business/architecture briefing as a single
landscape, print-ready PDF: business use case & functional flow, a "why this
is hard" problem infographic, a 7-column architecture flow diagram, and a
tech-design-considerations section (LLM vs. code, undeterminism handling,
evals at every stage).

Pipeline: same approach as docs/generate_project_pdfs.py — Python builds
semantic HTML + embedded CSS, a local headless Chrome instance prints it to
PDF. Landscape A4 throughout (the reference infographics this mirrors are
wide-format), color tokens reused from the existing doc design system.

Run:
    python3 generate_business_architecture_pdf.py
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
HTML_PATH = OUT_DIR / "health_sentinel_business_architecture.html"
PDF_PATH = OUT_DIR / "pdfs" / "health_sentinel_business_architecture.pdf"
PDF_PATH.parent.mkdir(parents=True, exist_ok=True)

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("google-chrome-stable") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]

# ---------------------------------------------------------------------------
# Design tokens (same palette as docs/generate_project_pdfs.py)
# ---------------------------------------------------------------------------

CSS = """
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: #1B2430;
  -webkit-font-smoothing: antialiased;
}
:root {
  --ink: #0A1220;
  --ink2: #142A52;
  --teal: #2F5FD9;
  --teal-deep: #1E3A8A;
  --teal-light: #7FA6FF;
  --amber: #B45309;
  --amber-bg: #FDECD3;
  --emerald: #15803D;
  --emerald-bg: #DCFCE7;
  --rose: #BE123C;
  --rose-bg: #FDE1E7;
  --indigo: #6D28D9;
  --indigo-bg: #EDE6FB;
  --sky: #0369A1;
  --sky-bg: #E0F2FE;
  --slate-900: #131C28;
  --slate-700: #33475A;
  --slate-500: #62788C;
  --slate-300: #D6E0E8;
  --slate-100: #EEF3F6;
  --card: #FFFFFF;
}
.page {
  width: 297mm; height: 210mm; position: relative; overflow: hidden;
  background: #F5F7FA; padding: 8mm 12mm;
}
.page + .page { page-break-before: always; }

.masthead { display: flex; align-items: center; justify-content: space-between; margin-bottom: 3mm; }
.brandmark { display: flex; align-items: center; gap: 3mm; }
.brand-badge {
  width: 12mm; height: 12mm; border-radius: 3mm;
  background: linear-gradient(155deg, var(--teal-light), var(--teal-deep));
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(10,20,40,0.25);
}
.brand-badge svg { width: 6.4mm; height: 6.4mm; }
.brand-name { font-size: 15pt; font-weight: 800; color: var(--ink); letter-spacing: -0.2px; }
.brand-sub { font-size: 7.6pt; color: var(--slate-500); font-weight: 600; letter-spacing: 0.3px; }
.sticky {
  background: #FFF7CC; border: 1px solid #E8D98A; border-radius: 1.5mm;
  padding: 2.4mm 4mm; font-size: 7.6pt; font-weight: 700; color: #6B5B10;
  max-width: 62mm; text-align: center; line-height: 1.35; transform: rotate(1deg);
  box-shadow: 1.5px 2px 3px rgba(0,0,0,0.08);
}

.title-band {
  background: linear-gradient(120deg, var(--ink) 0%, var(--teal-deep) 100%);
  border-radius: 3mm; padding: 4mm 8mm; margin-bottom: 4mm;
  display: flex; align-items: center; justify-content: space-between; gap: 8mm; color: #fff;
}
.title-band h1 { font-size: 18pt; font-weight: 800; margin: 0 0 1mm 0; letter-spacing: -0.2px; }
.title-band p { font-size: 8.6pt; color: #C9D6EA; margin: 0; max-width: 150mm; line-height: 1.4; }
.title-band .tb-right { font-size: 7.4pt; color: #AFC0DC; text-align: right; line-height: 1.6; white-space: nowrap; }

.section-label {
  display: flex; align-items: center; gap: 2.2mm; font-size: 8.8pt; font-weight: 800;
  color: var(--slate-900); text-transform: uppercase; letter-spacing: 0.5px; margin: 2.4mm 0 1.6mm 0;
}
.section-label .dot { width: 2.8mm; height: 2.8mm; border-radius: 1px; flex-shrink: 0; }
.dot-teal { background: var(--teal); } .dot-amber { background: var(--amber); }
.dot-rose { background: var(--rose); } .dot-emerald { background: var(--emerald); }
.dot-indigo { background: var(--indigo); } .dot-sky { background: var(--sky); }

p.lead { font-size: 8.4pt; line-height: 1.5; color: var(--slate-700); margin: 0 0 2mm 0; }

/* step pills (functional flow) */
.steps-row { display: flex; gap: 2.4mm; }
.step-pill {
  flex: 1; background: var(--card); border: 1px solid var(--slate-300); border-radius: 2.4mm;
  padding: 2.4mm 2.8mm; font-size: 7.3pt; color: var(--slate-700); display: flex; gap: 1.8mm; align-items: flex-start;
}
.step-pill .n {
  flex-shrink: 0; width: 5.2mm; height: 5.2mm; border-radius: 50%; background: var(--teal);
  color: #fff; font-size: 7.6pt; font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.step-pill b { color: var(--slate-900); }

/* cards / personas */
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; }
.card {
  background: var(--card); border-radius: 2.6mm; padding: 2.6mm 3mm;
  border: 1px solid var(--slate-300); border-top: 2.6px solid var(--teal);
  box-shadow: 0 1px 2px rgba(15,25,45,0.05);
}
.card.acc-amber { border-top-color: var(--amber); } .card.acc-rose { border-top-color: var(--rose); }
.card.acc-emerald { border-top-color: var(--emerald); } .card.acc-indigo { border-top-color: var(--indigo); }
.card.acc-sky { border-top-color: var(--sky); }
.card-icon {
  width: 7mm; height: 7mm; border-radius: 1.8mm; display: flex; align-items: center; justify-content: center;
  background: #E7EEFC; margin-bottom: 1.6mm;
}
.card-icon svg { width: 4mm; height: 4mm; }
.card.acc-amber .card-icon { background: var(--amber-bg); } .card.acc-rose .card-icon { background: var(--rose-bg); }
.card.acc-emerald .card-icon { background: var(--emerald-bg); } .card.acc-indigo .card-icon { background: var(--indigo-bg); }
.card.acc-sky .card-icon { background: var(--sky-bg); }
.card-title { font-size: 8.6pt; font-weight: 700; color: var(--slate-900); margin-bottom: 0.6mm; }
.card-desc { font-size: 7.2pt; line-height: 1.32; color: var(--slate-700); }

ul.tick { list-style: none; padding: 0; margin: 0; }
ul.tick li { position: relative; padding-left: 4.4mm; font-size: 7.4pt; line-height: 1.42; color: var(--slate-700); margin-bottom: 1.1mm; }
ul.tick li::before { content: ""; position: absolute; left: 0; top: 1.6mm; width: 2.2mm; height: 2.2mm; border-radius: 50%; background: var(--teal); }
ul.tick.amber li::before { background: var(--amber); }
ul.tick.rose li::before { background: var(--rose); }
ul.tick.emerald li::before { background: var(--emerald); }
ul.tick li b { color: var(--slate-900); }

/* ---------- problem infographic (page 2) ---------- */
.problem-head { display: flex; align-items: baseline; gap: 4mm; margin-bottom: 1mm; }
.why-badge { font-size: 30pt; font-weight: 900; color: var(--rose); letter-spacing: -1px; }
.problem-head h2 { font-size: 15pt; font-weight: 800; color: var(--ink); margin: 0; line-height: 1.18; }
.problem-sub { font-size: 8.6pt; color: var(--slate-700); margin: 0 0 3mm 0; max-width: 190mm; line-height: 1.45; }
.problem-body { display: grid; grid-template-columns: 1.05fr 0.85fr; gap: 6mm; align-items: start; }
.challenge-row { display: flex; gap: 2.6mm; align-items: flex-start; padding: 1.8mm 0; border-bottom: 1px solid var(--slate-100); }
.challenge-row:last-child { border-bottom: none; }
.chal-icon {
  flex-shrink: 0; width: 7.4mm; height: 7.4mm; border-radius: 50%; display: flex; align-items: center; justify-content: center;
}
.chal-icon svg { width: 4mm; height: 4mm; }
.chal-title { font-size: 8.4pt; font-weight: 700; color: var(--slate-900); margin-bottom: 0.4mm; }
.chal-desc { font-size: 7.2pt; line-height: 1.32; color: var(--slate-700); }
.photo-wrap { position: relative; border-radius: 3mm; overflow: hidden; height: 108mm; box-shadow: 0 2px 10px rgba(10,20,40,0.18); }
.photo-wrap img { width: 100%; height: 100%; object-fit: cover; }
.photo-wrap .illustration {
  width: 100%; height: 100%;
  background: radial-gradient(circle at 50% 38%, #2A3B5C 0%, #1B2740 55%, #101828 100%);
  display: flex; align-items: center; justify-content: center; position: relative;
}
.photo-wrap .illustration svg { width: 34mm; height: 34mm; opacity: 0.92; }
.bubble {
  position: absolute; background: #fff; border-radius: 3mm; padding: 1.6mm 3mm; font-size: 6.8pt; font-weight: 600;
  color: var(--ink); box-shadow: 0 2px 6px rgba(0,0,0,0.18); max-width: 42mm; line-height: 1.3;
}
.result-callout {
  margin-top: 3mm; background: var(--rose-bg); border-left: 3px solid var(--rose); border-radius: 2mm;
  padding: 2.6mm 4mm; font-size: 8pt; color: #6E1420; line-height: 1.4;
}
.result-callout b { font-weight: 800; }
.deserve-row { display: flex; gap: 4mm; margin-top: 2.6mm; align-items: center; justify-content: center; }
.deserve-item { display: flex; align-items: center; gap: 1.6mm; font-size: 7.6pt; font-weight: 700; color: var(--slate-700); }
.deserve-item svg { width: 4.2mm; height: 4.2mm; }

/* ---------- architecture flow diagram (page 3) ---------- */
.flowgrid { display: flex; align-items: stretch; gap: 0; margin-top: 1mm; }
.flowcol {
  flex: 1; background: var(--card); border: 1px solid var(--slate-300); border-radius: 2mm;
  margin-right: 2mm; padding: 2mm 1.8mm; display: flex; flex-direction: column;
}
.flowcol:last-child { margin-right: 0; }
.flowcol-head { display: flex; align-items: center; gap: 1.4mm; margin-bottom: 1.6mm; padding-bottom: 1.4mm; border-bottom: 1.4px solid var(--slate-200, #E4EAEF); }
.flowcol-num {
  flex-shrink: 0; width: 4.6mm; height: 4.6mm; border-radius: 50%; color: #fff; font-size: 6.8pt; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}
.flowcol-title { font-size: 6.9pt; font-weight: 800; color: var(--slate-900); line-height: 1.14; }
.flow-item { display: flex; gap: 1.2mm; align-items: flex-start; margin-bottom: 1.5mm; }
.flow-item .fi-icon { flex-shrink: 0; width: 4.2mm; height: 4.2mm; border-radius: 1mm; display: flex; align-items: center; justify-content: center; margin-top: 0.2mm; }
.flow-item .fi-icon svg { width: 2.6mm; height: 2.6mm; }
.flow-item .fi-text { font-size: 6.2pt; line-height: 1.28; color: var(--slate-700); }
.flow-item .fi-text b { display: block; font-size: 6.5pt; color: var(--slate-900); font-weight: 700; }
.flow-arrow { display: flex; align-items: center; justify-content: center; width: 4mm; color: var(--teal); font-size: 10pt; font-weight: 800; flex-shrink: 0; }

.infra-bar {
  margin-top: 3mm; background: linear-gradient(120deg, var(--ink) 0%, var(--teal-deep) 100%); border-radius: 2.4mm;
  padding: 2.2mm 5mm; display: flex; align-items: center; gap: 4mm; color: #fff;
}
.infra-bar .ib-main { font-size: 9pt; font-weight: 800; }
.infra-bar .ib-sub { font-size: 7pt; color: #C9D6EA; }
.infra-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2.4mm; margin-top: 2.4mm; }
.tagline-strip {
  margin-top: 2.4mm; display: flex; align-items: center; justify-content: center; gap: 2.4mm;
  font-size: 8pt; font-weight: 700; color: var(--emerald);
}
.tagline-strip svg { width: 4mm; height: 4mm; }

/* ---------- tech considerations tables ---------- */
table.kv { width: 100%; border-collapse: collapse; font-size: 7.3pt; }
table.kv th { text-align: left; font-size: 6.6pt; text-transform: uppercase; letter-spacing: 0.4px; color: var(--slate-500); padding: 1.2mm 2mm; border-bottom: 1.5px solid var(--slate-300); }
table.kv td { padding: 1.3mm 2mm; border-bottom: 1px solid var(--slate-100); color: var(--slate-700); vertical-align: top; }
table.kv tr:last-child td { border-bottom: none; }
.tag { display: inline-block; font-size: 6.2pt; font-weight: 700; padding: 0.5mm 1.8mm; border-radius: 20px; }
.tag-llm { background: var(--indigo-bg); color: var(--indigo); }
.tag-code { background: var(--sky-bg); color: var(--sky); }
.tag-hybrid { background: var(--amber-bg); color: #7A4A0A; }
.tag-human { background: #FFF3CD; color: #7A5B00; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 6.8pt; color: var(--teal-deep); background: #E7EEFC; padding: 0.3mm 1.2mm; border-radius: 1mm; }

.stat-tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2.2mm; }
.stat-tile { border-radius: 2.4mm; padding: 2.2mm 2.2mm; text-align: left; background: var(--slate-100); border: 1px solid var(--slate-300); }
.stat-tile .num { font-size: 13pt; font-weight: 800; color: var(--slate-900); line-height: 1; }
.stat-tile .label { font-size: 6.6pt; color: var(--slate-500); margin-top: 0.9mm; line-height: 1.26; font-weight: 600; }
.stat-tile.teal { background: #E7EEFC; border-color: #C1D2F5; } .stat-tile.amber { background: var(--amber-bg); border-color: #F3D3A6; }
.stat-tile.emerald { background: var(--emerald-bg); border-color: #BEE3CE; } .stat-tile.indigo { background: var(--indigo-bg); border-color: #D3C4F2; }
.stat-tile.rose { background: var(--rose-bg); border-color: #F0C2CC; }

.foot-note { position: absolute; bottom: 5mm; left: 12mm; right: 12mm; text-align: center; font-size: 6.6pt; color: var(--slate-500); }
"""

# ---------------------------------------------------------------------------
# Icon set (hand-drawn, license-free geometric line icons)
# ---------------------------------------------------------------------------

def icon(name: str, stroke: str = "#1E3A8A") -> str:
    c = f'fill="none" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
    paths = {
        "heart": f'<svg viewBox="0 0 24 24" {c}><path d="M12 20s-7.5-4.6-9.6-9.4C1 6.8 3 3.5 6.6 3.2c2-.2 3.7.9 5.4 2.9 1.7-2 3.4-3.1 5.4-2.9C21 3.5 23 6.8 21.6 10.6 19.5 15.4 12 20 12 20z"/></svg>',
        "shield": f'<svg viewBox="0 0 24 24" {c}><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg>',
        "check": f'<svg viewBox="0 0 24 24" {c}><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
        "alert": f'<svg viewBox="0 0 24 24" {c}><path d="M12 3.5L21.5 20h-19z"/><line x1="12" y1="9.5" x2="12" y2="14"/><circle cx="12" cy="16.8" r="0.4" fill="{stroke}"/></svg>',
        "users": f'<svg viewBox="0 0 24 24" {c}><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/><circle cx="17.5" cy="9" r="2.4"/><path d="M15.5 14c2.6.3 4.5 2 4.5 5"/></svg>',
        "message": f'<svg viewBox="0 0 24 24" {c}><path d="M4 5.5h16v11H9.5L5 20V16.5H4z"/></svg>',
        "layers": f'<svg viewBox="0 0 24 24" {c}><path d="M12 3.5l8 4.2-8 4.2-8-4.2z"/><path d="M4 12l8 4.2 8-4.2"/><path d="M4 15.8L12 20l8-4.2"/></svg>',
        "cpu": f'<svg viewBox="0 0 24 24" {c}><rect x="6.5" y="6.5" width="11" height="11" rx="1.4"/><rect x="10" y="10" width="4" height="4"/><path d="M9 3.5v3M15 3.5v3M9 17.5v3M15 17.5v3M3.5 9h3M3.5 15h3M17.5 9h3M17.5 15h3"/></svg>',
        "lock": f'<svg viewBox="0 0 24 24" {c}><rect x="5.5" y="10.5" width="13" height="9" rx="1.4"/><path d="M8 10.5V7.5a4 4 0 018 0v3"/></svg>',
        "clock": f'<svg viewBox="0 0 24 24" {c}><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
        "database": f'<svg viewBox="0 0 24 24" {c}><ellipse cx="12" cy="6" rx="7.5" ry="2.6"/><path d="M4.5 6v6c0 1.4 3.4 2.6 7.5 2.6s7.5-1.2 7.5-2.6V6"/><path d="M4.5 12v6c0 1.4 3.4 2.6 7.5 2.6s7.5-1.2 7.5-2.6v-6"/></svg>',
        "trend": f'<svg viewBox="0 0 24 24" {c}><path d="M4 16l5-6 4 3 6-8"/><path d="M15 5h4v4"/></svg>',
        "folder": f'<svg viewBox="0 0 24 24" {c}><path d="M3 6.5A1.5 1.5 0 014.5 5H9l2 2.5h8A1.5 1.5 0 0120.5 9v9A1.5 1.5 0 0119 19.5H4.5A1.5 1.5 0 013 18z"/></svg>',
        "route": f'<svg viewBox="0 0 24 24" {c}><circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="M5 8.2V13a4 4 0 004 4h4"/></svg>',
        "camera": f'<svg viewBox="0 0 24 24" {c}><path d="M4 8.5h3l1.5-2.5h7L17 8.5h3v10H4z"/><circle cx="12" cy="13.2" r="3.2"/></svg>',
        "flask": f'<svg viewBox="0 0 24 24" {c}><path d="M9 3h6M10 3v6.5L5.5 18a2 2 0 001.8 3h9.4a2 2 0 001.8-3L14 9.5V3"/><path d="M8 14h8"/></svg>',
        "watch": f'<svg viewBox="0 0 24 24" {c}><circle cx="12" cy="12" r="6.5"/><path d="M12 9v3.5l2 1.4"/><path d="M9 3.5h6M9 20.5h6"/></svg>',
        "sms": f'<svg viewBox="0 0 24 24" {c}><path d="M4 5.5h16v11H9.5L5 20V16.5H4z"/><path d="M8 9.5h8M8 12.5h5"/></svg>',
        "calendar": f'<svg viewBox="0 0 24 24" {c}><rect x="4" y="5.5" width="16" height="14.5" rx="1.4"/><path d="M4 10h16M8 3.5v4M16 3.5v4"/></svg>',
        "book": f'<svg viewBox="0 0 24 24" {c}><path d="M4 5.5c2-1 5-1 7 0v13c-2-1-5-1-7 0z"/><path d="M20 5.5c-2-1-5-1-7 0v13c2-1 5-1 7 0z"/></svg>',
        "gate": f'<svg viewBox="0 0 24 24" {c}><path d="M6 3.5v17M18 3.5v17"/><path d="M6 9h12M6 15h12"/></svg>',
        "scan": f'<svg viewBox="0 0 24 24" {c}><path d="M4 8V5.5A1.5 1.5 0 015.5 4H8M16 4h2.5A1.5 1.5 0 0120 5.5V8M20 16v2.5a1.5 1.5 0 01-1.5 1.5H16M8 20H5.5A1.5 1.5 0 014 18.5V16"/><line x1="4" y1="12" x2="20" y2="12"/></svg>',
        "brain": f'<svg viewBox="0 0 24 24" {c}><path d="M9 4.5a3 3 0 00-3 3v1a3 3 0 00-1.5 5.6A3 3 0 007 18h1M15 4.5a3 3 0 013 3v1a3 3 0 011.5 5.6A3 3 0 0117 18h-1M9 4.5v13.5M15 4.5v13.5"/></svg>',
        "gavel": f'<svg viewBox="0 0 24 24" {c}><path d="M14 5l5 5M6 13l5 5M4 20l6-6M11.5 6.5l6 6"/></svg>',
        "person": f'<svg viewBox="0 0 24 24" {c}><circle cx="12" cy="8" r="3.4"/><path d="M5.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5"/></svg>',
        "stethoscope": f'<svg viewBox="0 0 24 24" {c}><path d="M6 4v6a4 4 0 008 0V4M10 4H6M18 4h-4"/><circle cx="18" cy="16" r="2.4"/><path d="M18 4v8a4 4 0 01-4 4H9"/></svg>',
        "headset": f'<svg viewBox="0 0 24 24" {c}><path d="M4 14v-2a8 8 0 0116 0v2"/><rect x="3" y="13" width="4" height="6" rx="1.4"/><rect x="17" y="13" width="4" height="6" rx="1.4"/></svg>',
        "chart": f'<svg viewBox="0 0 24 24" {c}><path d="M4 19h16M7 16V9M12 16V5M17 16v-6"/></svg>',
        "leaf": f'<svg viewBox="0 0 24 24" {c}><path d="M5 19c9 0 14-5 14-14C10 5 5 10 5 19Z"/><path d="M5 19c2-4 5-7 9-9"/></svg>',
        "eye": f'<svg viewBox="0 0 24 24" {c}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.6"/></svg>',
    }
    return paths.get(name, paths["check"])


def masthead(sticky_text: str) -> str:
    return f"""
<div class="masthead">
  <div class="brandmark">
    <div class="brand-badge">{icon('heart', '#08152E')}</div>
    <div>
      <div class="brand-name">Health Sentinel</div>
      <div class="brand-sub">Guardrailed Multi-Agent Nutrition &amp; Lifestyle Assistant</div>
    </div>
  </div>
  <div class="sticky">{sticky_text}</div>
</div>
"""


def title_band(title: str, sub: str, right: list[str]) -> str:
    right_html = "<br/>".join(right)
    return f"""
<div class="title-band">
  <div><h1>{title}</h1><p>{sub}</p></div>
  <div class="tb-right">{right_html}</div>
</div>
"""


def wrap(pages: list[str]) -> str:
    body = "".join(pages)
    return f"""<!doctype html><html><head><meta charset="utf-8"/><style>{CSS}</style></head><body>{body}</body></html>"""


# ---------------------------------------------------------------------------
# PAGE 1 — Business use case & functional flow
# ---------------------------------------------------------------------------

def page1() -> str:
    steps_row1 = """
<div class="steps-row">
  <div class="step-pill"><div class="n">1</div><div><b>User logs data</b> &mdash; a meal (photo/text), a lab report, an activity entry, or connects a simulated MCP (iWatch, SMS, Calendar, medical docs).</div></div>
  <div class="step-pill"><div class="n">2</div><div><b>Consent &amp; rate-limit gates</b> &mdash; deterministic code hard-stops the run if Tier&nbsp;1 consent is missing or a limit is exceeded. No LLM sees the request first.</div></div>
  <div class="step-pill"><div class="n">3</div><div><b>Multi-agent reasoning</b> &mdash; vision, nutrition, medical-RAG, lab-report and trend agents run (five of them in a real parallel fan-out) to build a full picture.</div></div>
</div>
"""
    steps_row2 = """
<div class="steps-row" style="margin-top:2mm;">
  <div class="step-pill"><div class="n">4</div><div><b>Guardrail gate</b> routes to a human whenever confidence is low, the user is new, severity is high, or an upstream check already blocked something.</div></div>
  <div class="step-pill"><div class="n">5</div><div><b>Nutritionist review (HITL)</b> &mdash; a human approves, modifies, or rejects the flagged prediction/recommendation before it can reach the user.</div></div>
  <div class="step-pill"><div class="n">6</div><div><b>Deterministic verifier + report</b> &mdash; an authoritative code check re-validates the final state; the user receives trends, SAFE-category predictions, filtered recommendations, and a full audit trail.</div></div>
</div>
"""
    personas = [
        ("person", "End user", "Logs meals, connects data sources, reads the daily report.", "teal"),
        ("stethoscope", "Nutritionist reviewer", "Approves, modifies, or rejects flagged predictions within SLA.", "amber"),
        ("headset", "Support / on-call", "Investigates anomalies, guardrail breaches, model drift.", "rose"),
        ("chart", "Data scientist", "Reviews aggregated, anonymized accuracy by cohort.", "indigo"),
    ]
    personas_html = "".join(
        f"""<div class="card acc-{acc}"><div class="card-icon">{icon(ic, {'teal':'#1E3A8A','amber':'#B45309','rose':'#BE123C','indigo':'#6D28D9'}[acc])}</div>
        <div class="card-title">{t}</div><div class="card-desc">{d}</div></div>"""
        for ic, t, d, acc in personas
    )
    goals = [
        "Turn a meal (photo or text) + wearable/medical/calendar context into daily nutrition totals, SAFE-category predictions, and filtered recommendations.",
        "Ground every medical-context claim in the user's own documents (RAG), and refuse rather than fabricate when evidence is weak.",
        "Route every run through deterministic guardrail gates: consent, rate limits, blocked categories, confidence thresholds, severity, allergens.",
        "Escalate to a human nutritionist whenever confidence, novelty, or severity crosses a threshold.",
        "Keep a full, structured, hash-anonymized audit trail of every agent decision.",
        "Optimize LLM spend by routing cheap / mid / reasoning-tier models to the right pipeline stage.",
    ]
    non_goals = [
        "No real medical diagnosis, treatment, or medication guidance of any kind &mdash; lifestyle guidance only.",
        "No real OAuth / HealthKit / SMS-provider integrations &mdash; MCP connectors are simulated with deterministic synthetic data.",
        "No production-grade persistence yet &mdash; checkpointer, store and rate limiter are all in-memory today.",
    ]
    goals_html = "".join(f"<li>{g}</li>" for g in goals)
    non_goals_html = "".join(f"<li>{g}</li>" for g in non_goals)

    body = f"""
<div class="page">
  {masthead("Your health story.<br/>Guardrailed for life.")}
  {title_band(
      "Business Use Case &amp; Functional Flow",
      "A guardrailed, multi-agent nutrition &amp; lifestyle assistant &mdash; from raw meal/lab/activity data to a "
      "safe, explainable, human-reviewable report. Built on LangGraph, never a diagnosis.",
      ["<b>Status</b> Portfolio / demo build", "<b>Client</b> Streamlit", "<b>Orchestration</b> LangGraph StateGraph"],
  )}
  <div class="section-label"><span class="dot dot-teal"></span>Who it's for</div>
  <div class="grid-4">{personas_html}</div>

  <div class="section-label" style="margin-top:2.6mm;"><span class="dot dot-emerald"></span>Functional flow: from raw input to guardrailed report</div>
  {steps_row1}
  {steps_row2}

  <div class="grid-2" style="margin-top:2.6mm;">
    <div>
      <div class="section-label"><span class="dot dot-sky"></span>Goals</div>
      <ul class="tick">{goals_html}</ul>
    </div>
    <div>
      <div class="section-label"><span class="dot dot-rose"></span>Explicit non-goals (current build)</div>
      <ul class="tick rose">{non_goals_html}</ul>
    </div>
  </div>
</div>
"""
    return body


# ---------------------------------------------------------------------------
# PAGE 2 — Problem infographic (styled after the reference "WHY" infographic)
# ---------------------------------------------------------------------------

def page2() -> str:
    challenges = [
        ("folder", "Health data lives in seven different places", "Meals, lab PDFs, a wearable, texts, a calendar, and medical documents &mdash; nothing talks to anything else.", "sky"),
        ("flask", "Lab reports and thresholds are hard to read alone", "An HbA1c of 7.2% or a fused-confidence score means nothing without context and cross-referencing.", "amber"),
        ("alert", "Generic AI chatbots give confident, unsafe answers", "No allergy filter, no confidence cap, no refusal path &mdash; a hallucinated recommendation looks identical to a correct one.", "rose"),
        ("shield", "A wrong recommendation can be dangerous, not just wrong", "A peanut allergy, a blocked medical category, an over-bound calorie suggestion &mdash; these need hard stops, not good intentions.", "rose"),
        ("eye", "No accountability", "No audit trail, no human in the loop, no way to ask 'why did it say that' after the fact.", "indigo"),
        ("trend", "Patterns get missed", "One bad lab reading or a slow 90-day glucose drift is invisible without a system watching every source at once.", "emerald"),
    ]
    chal_html = "".join(
        f"""<div class="challenge-row">
          <div class="chal-icon" style="background:var(--{acc}-bg);">{icon(ic, {'sky':'#0369A1','amber':'#B45309','rose':'#BE123C','indigo':'#6D28D9','emerald':'#15803D'}[acc])}</div>
          <div><div class="chal-title">{t}</div><div class="chal-desc">{d}</div></div>
        </div>"""
        for ic, t, d, acc in challenges
    )
    deserve = [
        ("shield", "clear, guardrailed answers"),
        ("check", "evidence, not fabrication"),
        ("users", "a human in the loop"),
        ("lock", "private, consent-gated data"),
    ]
    deserve_html = "".join(
        f'<div class="deserve-item">{icon(ic, "#15803D")}<span>You deserve {t}</span></div>' for ic, t in deserve
    )

    body = f"""
<div class="page">
  {masthead("Same data.<br/>Different story.")}
  <div class="problem-head">
    <span class="why-badge">WHY</span>
    <h2>Fragmented health data makes personal nutrition guidance hard &mdash;<br/>and generic AI makes it risky.</h2>
  </div>
  <p class="problem-sub">
    A meal photo, a lab PDF, a wearable export, a text, a calendar &mdash; each one is a fragment. Turning fragments into
    a trustworthy answer means someone (or something) has to read all of them together, know what's medically off-limits,
    and be honest when the evidence isn't there. Most tools don't do that.
  </p>
  <div class="problem-body">
    <div>
      <div class="section-label" style="margin-top:0;"><span class="dot dot-rose"></span>The challenges</div>
      {chal_html}
      <div class="result-callout">
        <b>The result:</b> without guardrails, generic AI health advice risks unsafe recommendations, zero accountability,
        and a user who has no way to tell a correct answer from a confident-sounding wrong one.
      </div>
    </div>
    <div class="photo-wrap">
      <div class="illustration">{icon("person", "#E8ECF6")}</div>
      <div class="bubble" style="top:8mm; left:8mm;">Is this safe for my allergy?</div>
      <div class="bubble" style="top:28mm; right:6mm;">Why did it suggest this?</div>
      <div class="bubble" style="bottom:34mm; left:8mm;">Who checked this?</div>
      <div class="bubble" style="bottom:10mm; right:6mm;">Is my data private?</div>
    </div>
  </div>
  <div class="deserve-row">{deserve_html}</div>
  <div class="foot-note">Health Sentinel &mdash; Business Use Case &amp; Problem Framing</div>
</div>
"""
    return body


# ---------------------------------------------------------------------------
# PAGE 3 — Architecture flow diagram (7 columns, styled after the reference)
# ---------------------------------------------------------------------------

def flow_item(ic: str, title: str, desc: str, bg: str, stroke: str) -> str:
    return f"""<div class="flow-item"><div class="fi-icon" style="background:{bg};">{icon(ic, stroke)}</div>
      <div class="fi-text"><b>{title}</b>{desc}</div></div>"""


def flow_col(num: int, num_color: str, title: str, items_html: str) -> str:
    return f"""<div class="flowcol">
      <div class="flowcol-head"><div class="flowcol-num" style="background:{num_color};">{num}</div><div class="flowcol-title">{title}</div></div>
      {items_html}
    </div>"""


def page3() -> str:
    TEAL, AMBER, ROSE, EMERALD, INDIGO, SKY = "#2F5FD9", "#B45309", "#BE123C", "#15803D", "#6D28D9", "#0369A1"
    TEAL_BG, AMBER_BG, ROSE_BG, EMERALD_BG, INDIGO_BG, SKY_BG = "#E7EEFC", "#FDECD3", "#FDE1E7", "#DCFCE7", "#EDE6FB", "#E0F2FE"

    col1 = "".join([
        flow_item("camera", "Meal photo / text", "", TEAL_BG, TEAL),
        flow_item("flask", "Lab report (PDF / photo)", "", ROSE_BG, ROSE),
        flow_item("watch", "Activity (iWatch, simulated)", "", EMERALD_BG, EMERALD),
        flow_item("sms", "SMS (simulated)", "", AMBER_BG, AMBER),
        flow_item("calendar", "Calendar (simulated)", "", INDIGO_BG, INDIGO),
        flow_item("book", "Medical documents", "", SKY_BG, SKY),
    ])
    col2 = "".join([
        flow_item("gate", "consent_gate + rate_limit_gate", "code &mdash; hard stop", TEAL_BG, TEAL),
        flow_item("scan", "intake_agent", "hybrid, cheap tier", AMBER_BG, AMBER),
        flow_item("camera", "vision_agent", "LLM, cheap tier", AMBER_BG, AMBER),
        flow_item("flask", "lab_report_agent (extract)", "LLM, mid tier", AMBER_BG, AMBER),
    ])
    col3 = "".join([
        flow_item("layers", "Canonical food keys + macros", "computed deterministically", TEAL_BG, TEAL),
        flow_item("check", "Validated lab readings", "allowlist + physiological bounds", EMERALD_BG, EMERALD),
        flow_item("shield", "Consent &amp; audit state", "", INDIGO_BG, INDIGO),
        flow_item("gavel", "Confidence attached", "every reading, every prediction", ROSE_BG, ROSE),
    ])
    col4 = "".join([
        flow_item("database", "Chroma vector store", "medical docs, user-isolated", TEAL_BG, TEAL),
        flow_item("database", "SQLite metrics store", "90-day glucose/weight/sleep", EMERALD_BG, EMERALD),
        flow_item("cpu", "InMemoryStore", "preferences, progress notes", INDIGO_BG, INDIGO),
        flow_item("folder", "JSONL audit log", "every agent decision", AMBER_BG, AMBER),
    ])
    col5 = "".join([
        flow_item("book", "medical_rag_agent", "LLM + RAG, mid &mdash; refuses below evidence threshold", INDIGO_BG, INDIGO),
        flow_item("trend", "trend_agent", "code, deterministic", TEAL_BG, TEAL),
        flow_item("brain", "prediction_agent", "LLM, reasoning &mdash; SAFE-only", ROSE_BG, ROSE),
        flow_item("gate", "guardrail_gate + verifier", "code, authoritative", SKY_BG, SKY),
        flow_item("users", "nutritionist_review", "human &mdash; HITL interrupt", AMBER_BG, AMBER),
        flow_item("message", "recommendation + critic + insight", "LLM, mid/reasoning &mdash; advisory-only", INDIGO_BG, INDIGO),
    ])
    col6 = "".join([
        flow_item("chart", "Trends &amp; insights", "glucose, sleep, weight, stress", TEAL_BG, TEAL),
        flow_item("brain", "SAFE-category predictions", "", ROSE_BG, ROSE),
        flow_item("check", "Filtered recommendations", "allergen + calorie/exercise guardrails", EMERALD_BG, EMERALD),
        flow_item("message", "Ask Health Sentinel", "symptom Q&amp;A, evidence-linked", INDIGO_BG, INDIGO),
        flow_item("lock", "Consent &amp; data controls", "", SKY_BG, SKY),
    ])
    col7 = "".join([
        flow_item("person", "Individual user", "own guardrailed profile", TEAL_BG, TEAL),
        flow_item("stethoscope", "Nutritionist reviewer", "HITL approval queue", AMBER_BG, AMBER),
        flow_item("headset", "Support / on-call", "incident response", ROSE_BG, ROSE),
        flow_item("chart", "Data scientist", "bias &amp; model monitoring", INDIGO_BG, INDIGO),
    ])

    cols = [
        flow_col(1, TEAL, "Data Sources<br/>(multi-format input)", col1),
        flow_col(2, AMBER, "Ingestion &amp; Conversion", col2),
        flow_col(3, EMERALD, "Structured Health Data", col3),
        flow_col(4, INDIGO, "Health Memory &amp;<br/>Knowledge Base", col4),
        flow_col(5, ROSE, "Agentic AI Layer<br/>(reason &amp; analyze)", col5),
        flow_col(6, SKY, "User Outputs<br/>(applications)", col6),
        flow_col(7, TEAL, "End Users", col7),
    ]
    arrow = '<div class="flow-arrow">&rarr;</div>'
    flowgrid_html = cols[0]
    for c in cols[1:]:
        flowgrid_html += arrow + c

    infra = [
        ("database", "Storage layer", "Chroma (vectors) &middot; SQLite (metrics) &middot; InMemoryStore (prefs)", "teal"),
        ("shield", "Guardrail modules", "medical &middot; hallucination &middot; bias &middot; privacy &middot; rate_limit", "rose"),
        ("cpu", "LLM &amp; model routing", "cheap / mid (gpt-4o-mini) &middot; reasoning (gpt-4o) &middot; embeddings", "indigo"),
        ("lock", "Security &amp; privacy", "Tier 1&ndash;3 classification &middot; RBAC &middot; hashed user IDs &middot; full audit trail", "sky"),
    ]
    infra_html = "".join(
        f"""<div class="card acc-{acc}"><div class="card-icon">{icon(ic, {'teal':TEAL,'rose':ROSE,'indigo':INDIGO,'sky':SKY}[acc])}</div>
        <div class="card-title">{t}</div><div class="card-desc">{d}</div></div>"""
        for ic, t, d, acc in infra
    )

    body = f"""
<div class="page">
  {masthead("A healthier<br/>tomorrow, guardrailed.")}
  {title_band(
      "Architecture Flow",
      "From your data to a guardrailed insight &mdash; safely, transparently, and with your consent.",
      ["<b>Orchestrator</b> LangGraph StateGraph", "<b>Client</b> Streamlit", "<b>Checkpointer</b> MemorySaver"],
  )}
  <div class="flowgrid">{flowgrid_html}</div>
  <div class="infra-bar">
    <div style="flex-shrink:0;">{icon('brain', '#fff')}</div>
    <div><div class="ib-main">Orchestrator &mdash; LangGraph StateGraph</div><div class="ib-sub">Explicit nodes &amp; conditional edges &middot; real parallel fan-out/fan-in &middot; interrupt()-based HITL &middot; deterministic verifier gate</div></div>
  </div>
  <div class="infra-row">{infra_html}</div>
  <div class="tagline-strip">{icon('leaf', '#15803D')}Guardrailed &middot; Evidence-grounded &middot; Human-reviewed &middot; Cost-optimized &middot; Fully audited{icon('heart', '#15803D')}</div>
</div>
"""
    return body


# ---------------------------------------------------------------------------
# PAGE 4 — Tech design considerations: LLM vs. code, undeterminism handling
# ---------------------------------------------------------------------------

def page4() -> str:
    rows = [
        ("consent_gate / rate_limit_gate", "code", "&mdash;", "Hard-stops the run before any agent (or model call) happens."),
        ("intake_agent", "hybrid", "cheap", "Tagged attachments route deterministically; only untagged free text is LLM-classified."),
        ("vision_agent", "LLM", "cheap", "Meal-photo food recognition; &lt;0.50 confidence &rarr; forced manual entry."),
        ("nutrition_agent", "hybrid", "mid", "LLM maps text to canonical food keys; macros/micros are then summed from a fixed table &mdash; never an LLM guess."),
        ("medical_rag_agent", "LLM", "mid", "RAG over the user's own docs; refuses (does not fabricate) below a fused-score threshold."),
        ("activity / sms / calendar agents", "code", "&mdash;", "Simulated MCP connectors &mdash; no model call at all."),
        ("lab_report_agent", "hybrid", "mid", "LLM proposes readings; every one is checked against a metric allowlist + physiological bounds before it's persisted."),
        ("trend_agent", "code", "&mdash;", "Deterministic aggregation/threshold classification of historic metric series."),
        ("prediction_agent", "LLM", "reasoning", "SAFE-category-only; blocked-category hard stop; confidence capped at 0.92."),
        ("guardrail_gate / guardrail_verifier", "code", "&mdash;", "Authoritative, independent re-check of raw state &mdash; not the LLM's self-assessment."),
        ("nutritionist_review", "human", "&mdash;", "HITL interrupt(); a person approves, modifies, or rejects."),
        ("recommendation_agent", "hybrid", "mid", "LLM drafts; deterministic allergen / calorie / exercise guardrails run independently and can block on their own."),
        ("critic_agent / insight_agent", "LLM", "reasoning / mid", "Advisory-only &mdash; can never override the deterministic verifier or change severity/status."),
    ]
    tag_class = {"code": "tag-code", "LLM": "tag-llm", "hybrid": "tag-hybrid", "human": "tag-human"}
    rows_html = "".join(
        f"""<tr><td><b>{n}</b></td><td><span class="tag {tag_class[k]}">{k}</span></td><td>{tier}</td><td>{d}</td></tr>"""
        for n, k, tier, d in rows
    )

    undeterminism = [
        "<b>Confidence cap, always &le;0.92.</b> No LLM output is ever presented as more certain than that, no matter what the model reports.",
        "<b>Hallucination floor on vision.</b> Meal-photo recognition below 0.50 confidence is rejected outright and routed to manual entry, not silently accepted.",
        "<b>Deterministic bounds, checked in code.</b> Calorie (1200&ndash;3000/day) and exercise (&le;150 min/week) limits are enforced by Python, independent of what the LLM recommended.",
        "<b>Blocked medical categories are a hard stop, not a prompt instruction.</b> A category like heart disease is suppressed by <span class=\"mono\">is_blocked_category()</span> in code &mdash; it cannot be argued around by the model.",
        "<b>guardrail_verifier is authoritative; critic_agent is advisory.</b> The deterministic verifier re-derives pass/fail straight from state. The LLM critic's opinion is logged but can never override it.",
        "<b>RAG refuses instead of fabricating.</b> Below a 0.28 fused dense+lexical score, <span class=\"mono\">medical_rag_agent</span> returns <span class=\"mono\">refused=True</span> rather than answering from weak evidence.",
        "<b>Structured, typed model calls.</b> Every model call goes through one choke point (<span class=\"mono\">call_structured()</span>) that validates <span class=\"mono\">stop_reason</span> and schema before the response is trusted.",
        "<b>Prompts are versioned artifacts.</b> Stored in <span class=\"mono\">prompts.py</span>, not inline strings &mdash; every output can be traced back to the exact prompt version that produced it.",
    ]
    und_html = "".join(f"<li>{u}</li>" for u in undeterminism)

    body = f"""
<div class="page">
  {masthead("Deterministic where<br/>it must be.")}
  {title_band(
      "Tech Design Considerations",
      "Why LangGraph over an LLM-planned agent framework, exactly where each pipeline stage sits on the LLM&ndash;vs&ndash;code line, "
      "and how the system stays predictable even though the models inside it aren't.",
      ["<b>Chosen over</b> Deep Agents", "<b>Why</b> guardrails must be code, not prompts", "<b>Result</b> every hard stop is a graph edge or a Python <span class='mono'>if</span>"],
  )}
  <div class="section-label"><span class="dot dot-indigo"></span>LLM vs. code &mdash; every node in the pipeline</div>
  <table class="kv">
    <tr><th>Node</th><th>Type</th><th>Model tier</th><th>Role</th></tr>
    {rows_html}
  </table>
  <div class="section-label" style="margin-top:2.6mm;"><span class="dot dot-rose"></span>Handling LLM undeterminism</div>
  <ul class="tick" style="columns:2; column-gap:8mm;">{und_html}</ul>
</div>
"""
    return body


# ---------------------------------------------------------------------------
# PAGE 5 — Evals at every stage
# ---------------------------------------------------------------------------

def page5() -> str:
    checks = [
        "Blocked-category suppression &mdash; a prediction in a blocked category is never shown.",
        "Confidence never exceeds the 0.92 cap, across every prediction.",
        "Mandatory disclaimer present in every final report.",
        "Calorie bounds (1200&ndash;3000/day) enforced on every numeric suggestion.",
        "Rate limiting blocks an 11th same-day meal image.",
        "3-sigma anomaly detection flags an outlier reading instead of using it silently.",
        "RAG refusal-vs-answer &mdash; refuses when evidence is weak, answers (cited) when it isn't.",
        "Consent blocking &mdash; a run with missing Tier 1 consent executes zero agent nodes.",
        "HITL triggering &mdash; a new user's first-week predictions always route to nutritionist review.",
        "Deterministic verifier authority &mdash; a verifier failure always forces review, regardless of what the LLM critic concluded.",
        "End-to-end allergen blocking &mdash; a peanut-allergic user never receives a peanut-containing recommendation.",
    ]
    checks_html = "".join(f"<li>{c}</li>" for c in checks)

    adversarial = [
        "<b>Direct diagnosis requests</b> (&ldquo;do I have heart disease?&rdquo;) must be blocked at a 100% rate &mdash; a hard bar, not a target.",
        "<b>Cross-user RAG isolation</b> &mdash; <span class=\"mono\">medical_rag_agent</span> must never retrieve another user's document chunks.",
        "<b>Poison-data / anomaly injection</b> &mdash; an implausible reading must be flagged, never averaged in silently.",
    ]
    adv_html = "".join(f"<li>{a}</li>" for a in adversarial)

    body = f"""
<div class="page">
  {masthead("Trust, but<br/>verify every run.")}
  {title_band(
      "Evals At Every Stage",
      "A required pre-deploy gate, not a one-time check &mdash; offline deterministic checks safe for CI without an API key, "
      "plus an adversarial suite for the failure modes that matter most in a health-safety system.",
      ["<b>Harness</b> eval/run_eval.py", "<b>Status</b> 11 / 11 passing", "<b>Suites</b> unit + adversarial + RAG"],
  )}
  <div class="section-label"><span class="dot dot-emerald"></span>The 11 required checks</div>
  <ul class="tick emerald" style="columns:2; column-gap:8mm;">{checks_html}</ul>

  <div class="section-label" style="margin-top:2.8mm;"><span class="dot dot-rose"></span>Adversarial / red-team cases &mdash; hard bars, not targets</div>
  <ul class="tick rose">{adv_html}</ul>

  <div class="section-label" style="margin-top:2.8mm;"><span class="dot dot-teal"></span>At a glance</div>
  <div class="stat-tiles">
    <div class="stat-tile emerald"><div class="num">11/11</div><div class="label">required checks passing today</div></div>
    <div class="stat-tile teal"><div class="num">0</div><div class="label">checks that need a live API key to run in CI</div></div>
    <div class="stat-tile rose"><div class="num">100%</div><div class="label">required block rate on direct-diagnosis adversarial cases</div></div>
    <div class="stat-tile indigo"><div class="num">0.28</div><div class="label">fused-score refusal threshold for medical RAG</div></div>
    <div class="stat-tile amber"><div class="num">0.92</div><div class="label">hard confidence cap on every prediction</div></div>
  </div>
  <div class="foot-note">Health Sentinel &mdash; Business Use Case, Architecture Flow &amp; Tech Design Considerations</div>
</div>
"""
    return body


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("No Chrome/Chromium binary found for HTML->PDF conversion.")


def render_pdf(chrome_bin: str, html_path: Path, pdf_path: Path) -> None:
    subprocess.run(
        [
            chrome_bin, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
            "--print-to-pdf-no-header", f"--print-to-pdf={pdf_path}", str(html_path),
        ],
        check=True, capture_output=True,
    )


def main() -> None:
    html = wrap([page1(), page2(), page3(), page4(), page5()])
    HTML_PATH.write_text(html, encoding="utf-8")
    chrome_bin = find_chrome()
    render_pdf(chrome_bin, HTML_PATH, PDF_PATH)
    print(f"Generated {PDF_PATH}")


if __name__ == "__main__":
    main()
