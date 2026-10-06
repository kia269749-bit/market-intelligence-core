"""Opportunity scoring for research-only early opportunity watchlists.

The score surfaces promising setups before they clear the economic $5 floor.
It never approves a trade and never lowers the economic gate.
"""
from __future__ import annotations

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(v)))

def _norm(v, lo, hi):
    if hi <= lo:
        return 0.0
    return _clamp((float(v) - lo) / (hi - lo))

def score_opportunity(forecast, ranking=None, adaptive_context=None, trade_filter=None):
    forecast = forecast or {}
    ranking = ranking or {}
    adaptive_context = adaptive_context or {}
    trade_filter = trade_filter or {}

    direction = str(forecast.get("direction") or "").upper()
    if direction not in ("UP", "DOWN"):
        return {"score": 0.0, "label": "NONE", "early_watch": False,
                "reason": "not_directional"}

    confidence = _clamp(forecast.get("confidence", 0.0))
    agreement = _clamp(adaptive_context.get("agreement", 0.0))
    quality = _clamp(adaptive_context.get("quality_score", 0.0))
    regime = str(adaptive_context.get("regime") or "UNKNOWN").upper()
    expected = abs(float(forecast.get("expected_return_pct", 0.0)))

    # Opportunity strength is about setup quality, not whether the trade is
    # already profitable enough. Expected move gets a soft cap at 3%.
    move_score = _norm(expected, 0.0, 3.0)

    regime_bonus = {
        "TREND": 1.00,
        "MIXED": 0.85,
        "RANGE": 0.65,
        "HIGH_VOLATILITY": 0.45,
        "UNKNOWN": 0.70,
    }.get(regime, 0.70)

    ranking_score = _clamp(ranking.get("score", 0.0))
    components = {
        "confidence": confidence,
        "agreement": agreement,
        "quality": quality,
        "move": move_score,
        "ranking": ranking_score,
        "regime": regime_bonus,
    }
    score = 100.0 * (
        0.30 * confidence +
        0.20 * agreement +
        0.15 * quality +
        0.20 * move_score +
        0.10 * ranking_score +
        0.05 * regime_bonus
    )

    # A very strong setup with a positive but insufficient economic edge is an
    # early watch candidate. This does not alter trade_filter.status.
    net_move = float(trade_filter.get("net_move_pct", 0.0) or 0.0)
    policy_status = str(trade_filter.get("policy_status") or "")
    economic_block = trade_filter.get("reason") in (
        "expected_move_below_usd5_after_costs",
        "economic_floor_not_met_watchlist_only",
    )
    early_watch = (
        score >= 65.0
        and confidence >= 0.68
        and agreement >= 0.60
        and quality >= 0.90
        and regime in ("TREND", "MIXED")
        and policy_status in ("WATCH", "STRONG")
        and economic_block
        and net_move > 0.0
    )
    if early_watch:
        label = "EARLY_WATCH"
        reason = "strong_setup_below_economic_floor"
    elif score >= 75.0:
        label = "HIGH_POTENTIAL"
        reason = "strong_setup"
    elif score >= 60.0:
        label = "POTENTIAL"
        reason = "developing_setup"
    else:
        label = "LOW"
        reason = "weak_opportunity"

    return {
        "score": round(score, 2),
        "label": label,
        "early_watch": early_watch,
        "reason": reason,
        "components": {k: round(v, 4) for k, v in components.items()},
        "research_only": True,
        "live_orders": False,
    }
