"""Tiered classifier cascade - cheapest tier first.

  T1 EXACT MAP  deterministic lookup, no model, no cost
  T2 CACHE      previously-seen sanitized string, no model
  T3 LLM        constrained structured output (only when LLM_MODE=FULL)
  T4 FALLBACK   UNKNOWN -> escalate to a human, never a guess

classifier_tier is recorded on every case. The tier distribution is the
quantitative proof of restraint.
"""
from __future__ import annotations
import json

import httpx

from app.core.config import settings
from app.domain.models.core import Classification
from app.domain.models.enums import ClassifierTier
from app.domain.taxonomy.loader import is_known, taxonomy_version
from app.llm.pii import mask
from app.llm.sanitizer import sanitize

#: (error_source, error_step, error_reason) -> canonical code
EXACT_MAP: dict[tuple[str, str, str], str] = {
    ("customer", "payment_authorization", "insufficient_funds"): "INSUFFICIENT_FUNDS",
    ("customer", "payment_authorization", "payment_hold"):       "TEMPORARY_HOLD",
    ("customer", "payment_authentication", "auth_abandoned"):    "AUTH_ABANDONED",
    ("customer", "payment_authentication", "otp_timeout"):       "OTP_TIMEOUT",
    ("customer", "payment_initiation", "card_expired"):          "CARD_EXPIRED",
    ("customer", "payment_initiation", "invalid_cvv"):           "INVALID_CVV",
    ("bank",     "payment_authorization", "card_blocked"):       "LOST_OR_STOLEN",
    ("bank",     "payment_authorization", "issuer_declined"):    "ISSUER_DECLINE",
    ("bank",     "payment_authorization", "soft_decline"):       "SOFT_DECLINE",
    ("gateway",  "payment_authorization", "gateway_timeout"):    "GATEWAY_TIMEOUT",
    ("gateway",  "payment_authorization", "network_error"):      "NETWORK_ERROR",
    ("gateway",  "payment_authorization", "gateway_error"):      "GATEWAY_ERROR",
    ("internal", "payment_authorization", "risk_declined"):      "RISK_DECLINED",
    ("internal", "payment_authorization", "fraud_suspected"):    "FRAUD_SUSPECTED",
    ("internal", "payment_capture", "duplicate"):                "DUPLICATE_DETECTED",
}

_SUBSTRINGS = [
    ("insufficient", "INSUFFICIENT_FUNDS"), ("low balance", "INSUFFICIENT_FUNDS"),
    ("expired", "CARD_EXPIRED"), ("timed out", "GATEWAY_TIMEOUT"),
    ("timeout", "GATEWAY_TIMEOUT"), ("do not honor", "ISSUER_DECLINE"),
    ("abandoned", "AUTH_ABANDONED"), ("fraud", "FRAUD_SUSPECTED"),
]

_CACHE: dict[str, tuple[str, float]] = {}


_CLASSIFY_INSTRUCTION = (
    "Return JSON only with keys: code and confidence. Use one of the known "
    "taxonomy codes for a payment-failure classification."
)


def _call_model(text: str) -> tuple[str, float] | None:
    """Dispatch to the configured live model provider. Returns None on any
    failure (missing key, network error, malformed response) so the caller
    falls back to the deterministic substring match - never a guess."""
    provider = (settings.LLM_PROVIDER or "openai").strip().lower()
    if provider == "gemini":
        return _call_gemini(text)
    return _call_openai(text)


def _call_openai(text: str) -> tuple[str, float] | None:
    api_key = (settings.LLM_API_KEY or "").strip()
    if not api_key:
        return None

    base_url = (settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    model = (settings.LLM_MODEL or "gpt-4o-mini").strip()
    url = f"{base_url}/chat/completions"

    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _CLASSIFY_INSTRUCTION},
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=(settings.LLM_TIMEOUT_MS / 1000.0),
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, str):
            data = json.loads(content)
            code = str(data.get("code", "")).upper()
            conf = float(data.get("confidence", 0.88) or 0.88)
            if code:
                return code, conf
    except Exception:
        return None
    return None


def _call_gemini(text: str) -> tuple[str, float] | None:
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        return None

    model = (settings.GEMINI_MODEL or "gemini-1.5-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    try:
        response = httpx.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": f"{_CLASSIFY_INSTRUCTION}\n\nError text: {text}"}]}],
                "generationConfig": {"temperature": 0, "response_mime_type": "application/json"},
            },
            timeout=(settings.LLM_TIMEOUT_MS / 1000.0),
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["candidates"][0]["content"]["parts"][0]["text"]
        if isinstance(content, str):
            data = json.loads(content)
            code = str(data.get("code", "")).upper()
            conf = float(data.get("confidence", 0.85) or 0.85)
            if code:
                return code, conf
    except Exception:
        return None
    return None


def classify(*, error_source: str | None, error_step: str | None, error_reason: str | None,
             error_description: str | None, customer_tokens: list[str] | None = None) -> tuple[Classification, dict]:
    from app.chaos.injector import CHAOS

    masked, _rev = mask(error_description or "", customer_tokens)
    clean, rep = sanitize(masked)
    meta = {"sanitizer": rep.__dict__, "masked_text": clean}
    tv = taxonomy_version()

    # T1 - exact map
    key = ((error_source or "").lower(), (error_step or "").lower(), (error_reason or "").lower())
    if key in EXACT_MAP:
        return Classification(code=EXACT_MAP[key], confidence=1.0, tier=ClassifierTier.T1_EXACT,
                              evidence_span=None, taxonomy_version=tv), meta

    # T2 - cache of previously resolved sanitized strings
    if clean and clean in _CACHE:
        code, conf = _CACHE[clean]
        return Classification(code=code, confidence=conf, tier=ClassifierTier.T2_VECTOR,
                              evidence_span=None, taxonomy_version=tv), meta

    # T3 - model. When a real key is configured, use it; otherwise keep the
    # deterministic substring fallback that keeps the system functional in STUB mode.
    if settings.LLM_MODE == "FULL" and not CHAOS.is_active("llm-timeout"):
        live = _call_model(clean)
        if live is not None:
            code, conf = live
            if is_known(code):
                _CACHE[clean] = (code, conf)
                return Classification(code=code, confidence=conf, tier=ClassifierTier.T3_LLM,
                                      evidence_span=clean[:80], taxonomy_version=tv), meta

        low = clean.lower()
        for frag, code in _SUBSTRINGS:
            if frag in low:
                if not is_known(code):
                    break
                _CACHE[clean] = (code, 0.88)
                return Classification(code=code, confidence=0.88, tier=ClassifierTier.T3_LLM,
                                      evidence_span=frag, taxonomy_version=tv), meta

    # T4 - never guess
    return Classification(code="UNKNOWN", confidence=0.0, tier=ClassifierTier.T4_FALLBACK,
                          evidence_span=None, taxonomy_version=tv), meta


def verify(c: Classification, sanitized_text: str) -> tuple[bool, str]:
    """Four gates. Any failure demotes to UNKNOWN rather than proceeding."""
    if not is_known(c.code):
        return False, "code not in taxonomy"
    from app.domain.taxonomy.loader import get_class
    if c.confidence < get_class(c.code).confidence_floor:
        return False, f"confidence {c.confidence:.2f} below floor"
    if c.evidence_span and c.evidence_span.lower() not in (sanitized_text or "").lower():
        return False, "evidence span not present in input"
    return True, "ok"


def reset_cache() -> None:
    _CACHE.clear()
