"""Prompt-injection & adversarial-input guardrails (OWASP LLM01 Prompt
Injection, LLM07 System Prompt Leakage, LLM10 Unbounded Consumption).

Deterministic, code-enforced pre-filter for any free-text field that will be
concatenated into an LLM prompt (e.g. a future symptom-query agent) — this
runs *before* the text ever reaches a model, same spirit as
`guardrails/verifier.py` running before the LLM critic.

Pattern matching cannot catch every novel jailbreak on its own (see Simon
Willison, "I don't know how to solve prompt injection") — this is one layer
of defense-in-depth, meant to be paired with:
  1. Never splicing raw user text into the system prompt — only into a
     clearly delimited "user data" block the model is told to treat as data.
  2. A fixed, enumerated output schema (closed-set categories + citations),
     so even a successful injection has no free-form field to exploit.
  3. Re-running the existing deterministic guardrails (medical.py,
     verifier.py) on whatever the LLM returns, same as every other agent.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

MAX_QUERY_CHARS = 500

# LLM01 subtype: "attempt to change system rules".
INSTRUCTION_OVERRIDE_PATTERNS = [
    r"\bignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|preceding)\s+instructions?\b",
    r"\bdisregard\s+(the\s+)?(above|previous|prior)\b",
    r"\bforget\s+(everything|all)\s+(you|i)\s+(were\s+told|said)\b",
    r"\bnew\s+instructions?\s*:",
    r"\byou\s+are\s+now\s+in\s+(developer|debug|dan|unrestricted)\s+mode\b",
]

# LLM01 subtype: role-play / persona override ("act as", "pretend", "DAN").
ROLE_OVERRIDE_PATTERNS = [
    r"\bact\s+as\s+(an?\s+)?(unfiltered|unrestricted|jailbroken)\b",
    r"\bpretend\s+(you\s+are|to\s+be)\b",
    r"\byou\s+are\s+no\s+longer\b",
    r"\b(dan|do\s+anything\s+now)\b",
]

# LLM07: system-prompt leakage / instruction-extraction attempts.
PROMPT_EXFILTRATION_PATTERNS = [
    r"\b(reveal|print|show|repeat)\s+(your|the)\s+(system\s+)?(prompt|instructions)\b",
    r"\bwhat\s+(are|were)\s+your\s+(initial\s+)?instructions\b",
]

# LLM01 subtype: encoding attacks used to smuggle instructions past a filter.
ENCODING_ATTACK_PATTERNS = [
    r"\bbase64\b", r"\brot13\b", r"\bhex\s+encod", r"\bonly\s+in\s+(url|base64)\s+encoding\b",
]

# LLM01 subtype: embedding a fake conversation turn to confuse the model.
CONVERSATION_MOCKUP_PATTERNS = [r"^\s*(system|assistant)\s*:"]

_ALL_PATTERN_GROUPS = {
    "instruction_override": INSTRUCTION_OVERRIDE_PATTERNS,
    "role_override": ROLE_OVERRIDE_PATTERNS,
    "prompt_exfiltration": PROMPT_EXFILTRATION_PATTERNS,
    "encoding_attack": ENCODING_ATTACK_PATTERNS,
}

_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\u2060\ufeff"


@dataclass
class InjectionScanResult:
    clean_text: str
    flagged: bool
    categories: list[str] = field(default_factory=list)
    truncated: bool = False


def sanitize_user_text(text: str) -> tuple[str, bool]:
    """Normalizes unicode and strips zero-width/control characters used to
    hide or split injection payloads. Returns (clean_text, was_truncated)."""
    normalized = unicodedata.normalize("NFKC", text)  # folds homoglyph/full-width tricks
    for ch in _ZERO_WIDTH_CHARS:
        normalized = normalized.replace(ch, "")
    normalized = "".join(
        c for c in normalized if c in ("\n", "\t") or not unicodedata.category(c).startswith("C")
    )
    truncated = len(normalized) > MAX_QUERY_CHARS
    return normalized[:MAX_QUERY_CHARS], truncated


def scan_for_injection(text: str) -> InjectionScanResult:
    """Deterministic pattern scan against known OWASP LLM01 attack subtypes."""
    clean_text, truncated = sanitize_user_text(text)
    lowered = clean_text.lower()
    categories: list[str] = []

    for category, patterns in _ALL_PATTERN_GROUPS.items():
        if any(re.search(p, lowered, re.IGNORECASE | re.MULTILINE) for p in patterns):
            categories.append(category)

    if any(re.match(p, line.strip(), re.IGNORECASE) for p in CONVERSATION_MOCKUP_PATTERNS
           for line in clean_text.splitlines()):
        categories.append("conversation_mockup")

    return InjectionScanResult(clean_text=clean_text, flagged=bool(categories),
                                categories=categories, truncated=truncated)


def assert_safe_for_llm(text: str) -> tuple[bool, list[str], str]:
    """Returns (is_safe, issues, sanitized_text) — mirrors the (passed, issues)
    convention of guardrails/verifier.py. `is_safe=False` means the caller
    must refuse to forward this text to an LLM (log it, return a canned
    refusal, do not retry with a "smarter" prompt)."""
    if not text or not text.strip():
        return False, ["empty input"], ""

    result = scan_for_injection(text)
    issues = [f"possible prompt injection pattern detected: {c}" for c in result.categories]
    if result.truncated:
        issues.append(f"input truncated to {MAX_QUERY_CHARS} characters")

    return (not result.flagged, issues, result.clean_text)
