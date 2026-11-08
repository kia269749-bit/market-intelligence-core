"""Adaptive, regime-aware signal thresholds.

The policy is intentionally elastic: it tightens in noisy/range conditions and
loosens modestly when trend, agreement and data quality improve. It never
overrides the economic $4 minimum or creates orders.
"""
from __future__ import annotations
import math
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


def _unit_value(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None
    return number


def get_signal_policy(regime="UNKNOWN", quality_score=1.0, agreement=1.0,
                      leader_follower=False):
    """Return context-aware thresholds; invalid numeric inputs are rejected."""
    quality = _unit_value(quality_score)
    agree = _unit_value(agreement)
    if quality is None or agree is None:
        raise ValueError("quality_score and agreement must be finite values in [0, 1]")

    regime = str(regime or "UNKNOWN").upper()
    watch, strong = _BASE.get(regime, _BASE["UNKNOWN"])

    # Good data and strong cross-source agreement earn only a small relaxation.
    if quality >= 0.90:
        watch -= 0.02
        strong -= 0.01
    if agree >= 0.80:
        watch -= 0.02
        strong -= 0.01

    # Confirmed leader->follower evidence is confirmation, never a standalone trigger.
    if leader_follower:
        watch -= 0.02

    watch = max(0.58, min(0.80, watch))
    strong = max(watch + 0.08, min(0.90, strong))
    return SignalPolicy(regime, round(watch, 4), round(strong, 4))


def policy_decision(confidence, direction, regime="UNKNOWN", quality_score=1.0,
                    agreement=1.0, leader_follower=False):
    conf = _unit_value(confidence)
    quality = _unit_value(quality_score)
    agree = _unit_value(agreement)
    direction = str(direction or "").upper()

    if conf is None or quality is None or agree is None:
        return {
            "eligible": False, "status": "NO_TRADE", "reason": "invalid_input",
            "policy": None,
        }

    regime = str(regime or "UNKNOWN").upper()
    try:
        policy = get_signal_policy(regime, quality, agree, leader_follower)
    except (TypeError, ValueError, OverflowError):
        return {
            "eligible": False, "status": "NO_TRADE", "reason": "invalid_input",
            "policy": None,
        }

    if direction not in ("UP", "DOWN"):
        return {"eligible": False, "status": "NO_TRADE",
                "reason": "forecast_not_directional", "policy": policy.__dict__}

    if agree < policy.min_agreement:
        # Soft conflict can surface as WATCH only in clean TREND/MIXED regimes.
        soft_conflict_floor = max(policy.watch_confidence + 0.08, 0.68)
        if (agree >= 0.50 and conf >= soft_conflict_floor and quality >= 0.90
                and regime in ("TREND", "MIXED")):
            return {"eligible": True, "status": "WATCH",
                    "reason": "soft_source_conflict_watch_only",
                    "policy": policy.__dict__}
        return {"eligible": False, "status": "NO_TRADE",
                "reason": "weak_cross_source_agreement", "policy": policy.__dict__}

    if conf >= policy.strong_confidence:
        status = "STRONG"
    elif conf >= policy.watch_confidence:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    return {
        "eligible": status != "NO_TRADE",
        "status": status,
        "reason": "adaptive_threshold_passed" if status != "NO_TRADE"
                  else "confidence_below_adaptive_floor",
        "policy": policy.__dict__,
    }
