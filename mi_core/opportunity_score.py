"""Opportunity scoring for research-only early opportunity watchlists.

The score surfaces promising setups before they clear the economic $4 floor.
It never approves a trade and never lowers the economic gate.
"""
from __future__ import annotations
import math


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _clamp(v, lo=0.0, hi=1.0):
    number = _finite_number(v)
    if number is None:
        raise ValueError("value must be finite")
    return max(lo, min(hi, number))


def _norm(v, lo, hi):
    if hi <= lo:
        return 0.0
    return _clamp((_finite_number(v) - lo) / (hi - lo))


def _no_opportunity(reason):
    return {
        "score": 0.0, "label": "NONE", "early_watch": False,
        "reason": reason, "research_only": True, "live_orders": False,
    }


def score_opportunity(forecast, ranking=None, adaptive_context=None, trade_filter=None):
    forecast = forecast if isinstance(forecast, dict) else {}
    ranking = ranking if isinstance(ranking, dict) else {}
    adaptive_context = adaptive_context if isinstance(adaptive_context, dict) else {}
    trade_filter = trade_filter if isinstance(trade_filter, dict) else {}

    # Preserve the existing contract: explicit unavailable means no opportunity.
    if forecast.get("available") is False:
        return _no_opportunity("forecast_unavailable")

    direction = str(forecast.get("direction") or "").upper()
    if direction not in ("UP", "DOWN"):
        return _no_opportunity("not_directional")

    confidence = _finite_number(forecast.get("confidence", 0.0))
    agreement = _finite_number(adaptive_context.get("agreement", 0.0))
    quality = _finite_number(adaptive_context.get("quality_score", 0.0))
    expected = _finite_number(forecast.get("expected_return_pct", 0.0))
    ranking_score = _finite_number(ranking.get("score", 0.0))
    net_move = _finite_number(trade_filter.get("net_move_pct", 0.0) or 0.0)

    if (confidence is None or agreement is None or quality is None
            or expected is None or ranking_score is None or net_move is None
            or not 0.0 <= confidence <= 1.0
            or not 0.0 <= agreement <= 1.0
            or not 0.0 <= quality <= 1.0
            or not 0.0 <= ranking_score <= 1.0
            or expected < 0.0):
        return _no_opportunity("invalid_input")

    regime = str(adaptive_context.get("regime") or "UNKNOWN").upper()
    move_score = _norm(expected, 0.0, 3.0)
    regime_bonus = {
        "TREND": 1.00, "MIXED": 0.85, "RANGE": 0.65,
        "HIGH_VOLATILITY": 0.45, "UNKNOWN": 0.70,
    }.get(regime, 0.70)

    components = {
        "confidence": confidence, "agreement": agreement,
        "quality": quality, "move": move_score,
        "ranking": ranking_score, "regime": regime_bonus,
    }
    score = 100.0 * (
        0.30 * confidence + 0.20 * agreement + 0.15 * quality
        + 0.20 * move_score + 0.10 * ranking_score + 0.05 * regime_bonus
    )

    policy_status = str(trade_filter.get("policy_status") or "")
    economic_block = trade_filter.get("reason") in (
        "expected_move_below_usd4_after_costs",
        "economic_floor_not_met_watchlist_only",
    )
    early_watch = (
        score >= 60.0 and confidence >= 0.60 and agreement >= 0.55
        and quality >= 0.80 and regime in ("TREND", "MIXED")
        and policy_status in ("WATCH", "STRONG") and economic_block
        and net_move > 0.0
    )
    if early_watch:
        label, reason = "EARLY_WATCH", "strong_setup_below_economic_floor"
    elif score >= 75.0:
        label, reason = "HIGH_POTENTIAL", "strong_setup"
    elif score >= 60.0:
        label, reason = "POTENTIAL", "developing_setup"
    else:
        label, reason = "LOW", "weak_opportunity"

    return {
        "score": round(score, 2), "label": label,
        "early_watch": early_watch, "reason": reason,
        "components": {k: round(v, 4) for k, v in components.items()},
        "research_only": True, "live_orders": False,
    }
