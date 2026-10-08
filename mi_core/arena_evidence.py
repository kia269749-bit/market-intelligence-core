"""Evidence-driven entry discipline distilled from the public AI Trading Competition.

This is a research policy, not a strategy claim. The public arena currently shows
an unstable lesson: patience and selective entry produced strong accounts, while
the same style also failed for other models. We encode the discipline, not a
winning bot's rules.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ArenaEvidencePolicy:
    min_confidence: float = 0.68
    min_agreement: float = 0.60
    min_confluence: float = 0.20
    max_cascade_risk: float = 0.75
    min_edge_over_cost: float = 1.25

def evaluate_entry_discipline(
    *,
    side: str,
    confidence: float,
    agreement: float,
    confluence: float,
    cascade_risk: float,
    edge_over_cost: float | None = None,
    named_reason: bool = False,
    regime: str = "UNKNOWN",
    policy: ArenaEvidencePolicy | None = None,
) -> dict:
    """Return a conservative, auditable patience/readiness decision.

    edge_over_cost is gross expected edge divided by estimated round-trip cost.
    When unavailable, the cost test is marked unknown rather than fabricated.
    """
    p = policy or ArenaEvidencePolicy()
    side = str(side or "FLAT").upper()
    reasons: list[str] = []

    if side not in ("LONG", "SHORT"):
        reasons.append("not_directional")
    if float(confidence) < p.min_confidence:
        reasons.append("confidence_below_patience_floor")
    if float(agreement) < p.min_agreement:
        reasons.append("cross_source_conflict")
    if float(confluence) < p.min_confluence:
        reasons.append("insufficient_confluence")
    if float(cascade_risk) > p.max_cascade_risk:
        reasons.append("cascade_risk_too_high")
    if edge_over_cost is not None and float(edge_over_cost) < p.min_edge_over_cost:
        reasons.append("edge_not_large_enough_after_cost_buffer")
    if not named_reason:
        reasons.append("no_named_entry_reason")

    if str(regime).upper() in ("RANGE", "HIGH_VOLATILITY"):
        if float(confidence) < p.min_confidence + 0.05:
            reasons.append("noisy_regime_requires_extra_confirmation")

    eligible = not reasons
    patience_score = 1.0
    patience_score -= 0.20 if float(confidence) < p.min_confidence else 0.0
    patience_score -= 0.20 if float(agreement) < p.min_agreement else 0.0
    patience_score -= 0.20 if float(confluence) < p.min_confluence else 0.0
    patience_score -= 0.20 if float(cascade_risk) > p.max_cascade_risk else 0.0
    patience_score -= 0.20 if edge_over_cost is not None and float(edge_over_cost) < p.min_edge_over_cost else 0.0

    return {
        "eligible": eligible,
        "status": "PATIENT_ENTRY" if eligible else "WAIT",
        "patience_score": round(max(0.0, patience_score), 4),
        "cost_test": "PASS" if edge_over_cost is not None and float(edge_over_cost) >= p.min_edge_over_cost else "UNKNOWN",
        "reasons": reasons,
        "policy": {
            "min_confidence": p.min_confidence,
            "min_agreement": p.min_agreement,
            "min_confluence": p.min_confluence,
            "max_cascade_risk": p.max_cascade_risk,
            "min_edge_over_cost": p.min_edge_over_cost,
        },
        "evidence_basis": [
            "selective_entry_over_churn",
            "named_reason_required",
            "regime_aware_confirmation",
            "cost_aware_edge",
            "learning_filters_must_prove_themselves",
        ],
        "research_only": True,
        "live_orders": False,
    }
