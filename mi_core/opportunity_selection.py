"""Opportunity-preserving signal selection for research-only trading signals.
The selector is deliberately a ranking layer, not a blanket signal suppressor.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class OpportunityConfig:
    min_direction_confidence: float = 0.52
    min_data_quality: float = 0.60
    min_expected_edge_pct: float = 0.0
    cost_safety_multiplier: float = 1.15
    strong_score: float = 0.78
    good_score: float = 0.66
    watch_score: float = 0.54

def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def _num(value, default=None):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if isfinite(value) else default

def opportunity_score(*, confidence, edge=0.0, agreement=0.0, data_quality=1.0,
                      regime_fit=0.5, timing=0.5, smart_money=0.0,
                      fomo_support=0.0, crowding=0.0, conflict=0.0) -> float:
    positive = (
        0.24 * _clip(confidence) + 0.18 * _clip(edge)
        + 0.14 * _clip(agreement) + 0.10 * _clip(data_quality)
        + 0.10 * _clip(regime_fit) + 0.10 * _clip(timing)
        + 0.07 * _clip(smart_money) + 0.07 * _clip(fomo_support)
    )
    penalty = 0.06 * _clip(crowding) + 0.06 * _clip(conflict)
    return round(_clip(positive - penalty), 6)

def select_opportunity(*, direction, confidence, expected_move_pct=None,
                       modeled_cost_pct=None, edge=0.0, agreement=0.0,
                       data_quality=1.0, regime_fit=0.5, timing=0.5,
                       smart_money=0.0, fomo_support=0.0, crowding=0.0,
                       conflict=0.0, config=None) -> dict:
    cfg = config or OpportunityConfig()
    direction = str(direction or "").upper()
    confidence = _num(confidence, -1.0)
    data_quality = _num(data_quality, 0.0)

    hard_reasons = []
    if direction not in {"LONG", "SHORT"}:
        hard_reasons.append("not_directional")
    if confidence is None or confidence < cfg.min_direction_confidence:
        hard_reasons.append("confidence_too_low")
    if data_quality is None or data_quality < cfg.min_data_quality:
        hard_reasons.append("data_quality_critical")

    expected = _num(expected_move_pct)
    costs = _num(modeled_cost_pct)
    cost_status = "UNAVAILABLE"
    if expected is not None and costs is not None:
        required = costs * cfg.cost_safety_multiplier
        cost_status = "PASS" if expected >= required else "FAIL"
        if cost_status == "FAIL":
            hard_reasons.append("expected_move_below_cost_floor")

    score = opportunity_score(
        confidence=confidence if confidence is not None else 0.0,
        edge=edge, agreement=agreement,
        data_quality=data_quality if data_quality is not None else 0.0,
        regime_fit=regime_fit, timing=timing, smart_money=smart_money,
        fomo_support=fomo_support, crowding=crowding, conflict=conflict,
    )
    if hard_reasons:
        status = "NO_TRADE"
    elif score >= cfg.strong_score:
        status = "STRONG"
    elif score >= cfg.good_score:
        status = "GOOD"
    elif score >= cfg.watch_score:
        status = "WATCH"
    else:
        status = "EARLY_OPPORTUNITY"

    return {
        "direction": direction, "status": status, "eligible": status != "NO_TRADE",
        "score": score, "confidence": round(confidence, 6) if confidence is not None else None,
        "expected_move_pct": expected, "modeled_cost_pct": costs,
        "cost_status": cost_status, "hard_reasons": tuple(hard_reasons),
        "research_only": True, "live_orders": False,
    }

def rank_opportunities(opportunities):
    return sorted(
        list(opportunities),
        key=lambda row: (
            bool(row.get("eligible")), float(row.get("score", 0.0)),
            float(row.get("confidence") or 0.0),
        ),
        reverse=True,
    )
