"""PII masking.

Placeholders use guillemets, NOT angle brackets: the injection sanitizer strips
HTML-like tags and would otherwise destroy the masks it is meant to preserve. Runs BEFORE anything reaches Zone 1 and before error_raw is persisted.
The reverse map lives in process memory for the call only - never logged, never stored."""
from __future__ import annotations
import re

_PATTERNS = [
    ("CARD",  re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("EMAIL", re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    ("VPA",   re.compile(r"\b[\w.-]{2,}@(?:ok\w+|paytm|ybl|upi|axl|ibl)\b", re.I)),
    ("PHONE", re.compile(r"\b(?:\+91[- ]?|0)?[6-9]\d{9}\b")),
    ("IFSC",  re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("ACCT",  re.compile(r"\b\d{9,18}\b")),
]


def _luhn(s: str) -> bool:
    d = [int(c) for c in s if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    tot, alt = 0, False
    for x in reversed(d):
        if alt:
            x *= 2
            if x > 9:
                x -= 9
        tot += x
        alt = not alt
    return tot % 10 == 0


def mask(text: str, extra_tokens: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """Returns (masked_text, reverse_map). Reverse map must not leave the process."""
    if not text:
        return "", {}
    out, rev, counters = text, {}, {}
    for token in (extra_tokens or []):
        if token and len(token) > 2 and token in out:
            counters["NAME"] = counters.get("NAME", 0) + 1
            ph = f"«NAME_{counters['NAME']}»"
            rev[ph] = token
            out = out.replace(token, ph)
    for label, pat in _PATTERNS:
        def _sub(m):
            val = m.group(0)
            if label == "CARD" and not _luhn(val):
                return val
            counters[label] = counters.get(label, 0) + 1
            ph = f"«{label}_{counters[label]}»"
            rev[ph] = val
            return ph
        out = pat.sub(_sub, out)
    return out, rev


def contains_pii(text: str) -> bool:
    masked, rev = mask(text)
    return bool(rev)
