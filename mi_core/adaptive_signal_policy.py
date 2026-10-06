"""Adaptive, regime-aware signal thresholds.

The policy is intentionally elastic: it tightens in noisy/range conditions and
loosens modestly when trend, agreement and data quality improve. It never
overrides the economic $5 minimum or creates orders.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SignalPolicy:
    regime: str
    watch_confidence: float
    strong_confidence: float
    min_agreement: float = 0.60


_BASE = {
    "TREND": (0.60, 0.72),
    "RANGE": (0.70, 0.80),
    "MIXED": (0.64, 0.75),
    "HIGH_VOLATILITY": (0.75, 0.82),
    "UNKNOWN": (0.66, 0.78),
}


def get_signal_policy(regime="UNKNOWN", quality_score=1.0, agreement=1.0,
                      leader_follower=False):
    """Return context-aware thresholds without changing economic requirements."""
    regime = str(regime or "UNKNOWN").upper()
    watch, strong = _BASE.get(regime, _BASE["UNKNOWN"])

    # Good data and strong cross-source agreement earn only a small relaxation.
    if float(quality_score) >= 0.90:
        watch -= 0.02
        strong -= 0.01
    if float(agreement) >= 0.80:
        watch -= 0.02
        strong -= 0.01

    # Confirmed leader->follower evidence is useful confirmation, never a
    # standalone trigger, so its threshold benefit is deliberately small.
    if leader_follower:
        watch -= 0.02

    # Keep the policy bounded. Never turn a weak forecast into a trade.
    watch = max(0.58, min(0.80, watch))
    strong = max(watch + 0.08, min(0.90, strong))
    return SignalPolicy(regime, round(watch, 4), round(strong, 4))


def policy_decision(confidence, direction, regime="UNKNOWN", quality_score=1.0,
                    agreement=1.0, leader_follower=False):
    policy = get_signal_policy(regime, quality_score, agreement, leader_follower)
    confidence = float(confidence)
    direction = str(direction or "").upper()
    if direction not in ("UP", "DOWN"):
        return {"eligible": False, "status": "NO_TRADE", "reason": "forecast_not_directional",
                "policy": policy.__dict__}
    if float(agreement) < policy.min_agreement:
        return {"eligible": False, "status": "NO_TRADE", "reason": "weak_cross_source_agreement",
                "policy": policy.__dict__}
    if confidence >= policy.strong_confidence:
        status = "STRONG"
    elif confidence >= policy.watch_confidence:
        status = "WATCH"
    else:
        status = "NO_TRADE"
    return {"eligible": status != "NO_TRADE", "status": status,
            "reason": "adaptive_threshold_passed" if status != "NO_TRADE" else "confidence_below_adaptive_floor",
            "policy": policy.__dict__}
