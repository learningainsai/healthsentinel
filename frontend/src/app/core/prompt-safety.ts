// TS mirror of guardrails/prompt_injection.py, for demoing the intended
// "screen before it reaches an LLM" flow in this client-only prototype.
// NOT a security boundary — client code is fully visible/bypassable; the
// authoritative check must run server-side (see prompt_injection.py) once a
// real backend LLM call exists.

const INSTRUCTION_OVERRIDE_PATTERNS: RegExp[] = [
  /\bignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|preceding)\s+instructions?\b/i,
  /\bdisregard\s+(the\s+)?(above|previous|prior)\b/i,
  /\bforget\s+(everything|all)\s+(you|i)\s+(were\s+told|said)\b/i,
  /\bnew\s+instructions?\s*:/i,
  /\byou\s+are\s+now\s+in\s+(developer|debug|dan|unrestricted)\s+mode\b/i,
];

const ROLE_OVERRIDE_PATTERNS: RegExp[] = [
  /\bact\s+as\s+(an?\s+)?(unfiltered|unrestricted|jailbroken)\b/i,
  /\bpretend\s+(you\s+are|to\s+be)\b/i,
  /\byou\s+are\s+no\s+longer\b/i,
  /\b(dan|do\s+anything\s+now)\b/i,
];

const PROMPT_EXFILTRATION_PATTERNS: RegExp[] = [
  /\b(reveal|print|show|repeat)\s+(your|the)\s+(system\s+)?(prompt|instructions)\b/i,
  /\bwhat\s+(are|were)\s+your\s+(initial\s+)?instructions\b/i,
];

const ENCODING_ATTACK_PATTERNS: RegExp[] = [
  /\bbase64\b/i, /\brot13\b/i, /\bhex\s+encod/i, /\bonly\s+in\s+(url|base64)\s+encoding\b/i,
];

const CONVERSATION_MOCKUP_PATTERN = /^\s*(system|assistant)\s*:/i;

const PATTERN_GROUPS: Record<string, RegExp[]> = {
  instruction_override: INSTRUCTION_OVERRIDE_PATTERNS,
  role_override: ROLE_OVERRIDE_PATTERNS,
  prompt_exfiltration: PROMPT_EXFILTRATION_PATTERNS,
  encoding_attack: ENCODING_ATTACK_PATTERNS,
};

const MAX_QUERY_CHARS = 500;
const ZERO_WIDTH_CHARS = /[\u200b\u200c\u200d\u2060\ufeff]/g;

export interface InjectionCheckResult {
  safe: boolean;
  issues: string[];
  cleanText: string;
}

export function sanitizeUserText(text: string): { cleanText: string; truncated: boolean } {
  const normalized = text.normalize('NFKC').replace(ZERO_WIDTH_CHARS, '');
  const truncated = normalized.length > MAX_QUERY_CHARS;
  return { cleanText: normalized.slice(0, MAX_QUERY_CHARS), truncated };
}

export function assertSafeForLlm(text: string): InjectionCheckResult {
  if (!text || !text.trim()) {
    return { safe: false, issues: ['empty input'], cleanText: '' };
  }

  const { cleanText, truncated } = sanitizeUserText(text);
  const categories: string[] = [];

  for (const [category, patterns] of Object.entries(PATTERN_GROUPS)) {
    if (patterns.some((p) => p.test(cleanText))) {
      categories.push(category);
    }
  }
  if (cleanText.split('\n').some((line) => CONVERSATION_MOCKUP_PATTERN.test(line.trim()))) {
    categories.push('conversation_mockup');
  }

  const issues = categories.map((c) => `possible prompt injection pattern detected: ${c}`);
  if (truncated) issues.push(`input truncated to ${MAX_QUERY_CHARS} characters`);

  return { safe: categories.length === 0, issues, cleanText };
}
