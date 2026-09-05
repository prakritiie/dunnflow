"""Seeded synthetic failure generator.

Distribution matches the frontend's FAILURE_CLASSES exactly and sums to N.
Same seed produces byte-identical output, which is what makes the dual-arm
comparison a result rather than an anecdote.
"""
from __future__ import annotations
import random
from dataclasses import dataclass

#: (code, family, weight) - long-tailed, mirrors real dunning volumes
DISTRIBUTION = [
    ("INSUFFICIENT_FUNDS", "LIQUIDITY",    0.2225),
    ("AUTH_ABANDONED",     "BEHAVIORAL",   0.1775),
    ("CARD_EXPIRED",       "INSTRUMENT",   0.1350),
    ("NETWORK_ERROR",      "TRANSIENT",    0.1175),
    ("ISSUER_DECLINE",     "ISSUER",       0.1025),
    ("RISK_DECLINED",      "RISK",         0.0950),
    ("GATEWAY_TIMEOUT",    "AMBIGUITY",    0.0550),
    ("DUPLICATE_DETECTED", "OPERATIONAL",  0.0450),
    ("SOFT_DECLINE",       "ISSUER",       0.0300),
    ("UNKNOWN",            "UNCLASSIFIED", 0.0200),
]

SIGNALS = {
    "INSUFFICIENT_FUNDS": ("customer", "payment_authorization", "insufficient_funds", "Insufficient funds in account"),
    "AUTH_ABANDONED":     ("customer", "payment_authentication", "auth_abandoned", "Customer did not complete authentication"),
    "CARD_EXPIRED":       ("customer", "payment_initiation", "card_expired", "Card has expired"),
    "NETWORK_ERROR":      ("gateway", "payment_authorization", "network_error", "Upstream network error"),
    "ISSUER_DECLINE":     ("bank", "payment_authorization", "issuer_declined", "Issuer declined - do not honor"),
    "RISK_DECLINED":      ("internal", "payment_authorization", "risk_declined", "Blocked by risk engine"),
    "GATEWAY_TIMEOUT":    ("gateway", "payment_authorization", "gateway_timeout", "Gateway timed out awaiting response"),
    "DUPLICATE_DETECTED": ("internal", "payment_capture", "duplicate", "Duplicate charge detected"),
    "SOFT_DECLINE":       ("bank", "payment_authorization", "soft_decline", "Temporary issuer decline"),
    "UNKNOWN":            ("gateway", "unknown_step", "zz_unmapped_9911", "ERR-9911 unmapped issuer response blob"),
}

MERCHANTS = ["MID-RAZR-8472", "MID-RAZR-9103", "MID-RAZR-7741", "MID-RAZR-6612"]

#: Free-text variants that do NOT match the classifier's T1 exact-map keys.
#: A minority of cases get one of these instead of the clean SIGNALS text, so
#: T1 genuinely misses and the case falls through to T2/T3 (live model, when
#: configured) or T4 UNKNOWN - never a guess. Roughly half are messy paraphrases
#: of a known class (recoverable via substring match or a real model call);
#: the rest are genuinely novel text a keyword table cannot resolve, which is
#: the honest case for why a model tier exists at all.
FREE_TEXT_VARIANTS = [
    ("bank", "payment_authorization", "account_frozen_audit",
     "bank_declined: customer account frozen in audit"),
    ("gateway", "payment_authorization", "origin_handshake_522",
     "gateway returned unexpected 522, origin connection timed out mid-handshake"),
    ("customer", "payment_initiation", "reissue_pending",
     "card expired last month per issuer records, customer requested reissue"),
    ("bank", "payment_authorization", "salary_credit_pending",
     "insufficient balance flagged by core banking, pending salary credit"),
    ("internal", "payment_authorization", "dispute_pending",
     "customer disputed the charge via mobile banking app, requesting explanation before retry"),
    ("gateway", "payment_authorization", "decline_code_unparseable",
     "issuer message garbled: 91XX unable to parse decline code"),
]
#: Fraction of the batch that receives free-text (unmapped) error signals.
FREE_TEXT_RATE = 0.12


@dataclass(frozen=True)
class SyntheticCase:
    case_ref: str
    merchant_id: str
    obligation_ref: str
    failure_class: str
    failure_family: str
    amount_minor: int
    raw_error: dict


def _counts(n: int) -> list[tuple[str, str, int]]:
    """Largest-remainder allocation so counts sum to exactly n."""
    raw = [(c, f, w * n) for c, f, w in DISTRIBUTION]
    base = [(c, f, int(x)) for c, f, x in raw]
    rem = n - sum(b[2] for b in base)
    order = sorted(range(len(raw)), key=lambda i: raw[i][2] - int(raw[i][2]), reverse=True)
    counts = [list(b) for b in base]
    for i in range(rem):
        counts[order[i % len(order)]][2] += 1
    return [(c, f, k) for c, f, k in counts]


def generate(seed: int, n: int) -> list[SyntheticCase]:
    rng = random.Random(seed)
    plan = _counts(n)
    slots: list[tuple[str, str]] = []
    for code, fam, k in plan:
        slots.extend([(code, fam)] * k)
    rng.shuffle(slots)

    out: list[SyntheticCase] = []
    for i, (code, fam) in enumerate(slots, start=1):
        if rng.random() < FREE_TEXT_RATE:
            src, step, reason, desc = FREE_TEXT_VARIANTS[rng.randrange(len(FREE_TEXT_VARIANTS))]
        else:
            src, step, reason, desc = SIGNALS[code]
        # log-normal-ish amounts, integer paise, never a float in the money path
        amount = int(round(rng.lognormvariate(8.6, 1.15))) * 100
        amount = max(9900, min(amount, 9_000_000))
        is_sub = rng.random() < 0.4
        out.append(SyntheticCase(
            case_ref=f"CASE-{i:04d}",
            merchant_id=rng.choice(MERCHANTS),
            obligation_ref=(f"SUB-{8821000 + i}" if is_sub else f"PAY-{2847000 + i}"),
            failure_class=code, failure_family=fam, amount_minor=amount,
            raw_error={"source": src, "step": step, "reason": reason, "description": desc},
        ))
    return out
