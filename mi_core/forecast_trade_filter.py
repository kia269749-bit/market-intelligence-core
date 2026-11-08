"""Capital-aware filtering for multi-asset forecast candidates.

Research-only. A forecast is never treated as a trade merely because confidence
is high. The filter requires directional agreement, sufficient confidence and
a modeled net profit floor after round-trip costs.
"""
from __future__ import annotations
import math
from .trade_economics import evaluate_capital_target
from .adaptive_signal_policy import policy_decision


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def evaluate_forecast(forecast, capital_usd=500.0, min_profit_usd=4.0,
                      preferred_profit_usd=10.0, min_confidence=None,
                      exchange="hyperliquid_perps", order_type="taker",
                      regime="UNKNOWN", quality_score=1.0, agreement=1.0,
                      leader_follower=False):
    if not isinstance(forecast, dict) or not forecast.get("available"):
        return {"approved": False, "status": "NO_TRADE",
                "reason": "forecast_unavailable",
                "research_only": True, "live_orders": False}

    direction = str(forecast.get("direction") or "").upper()
    confidence = _finite_number(forecast.get("confidence", 0.0))
    expected = _finite_number(forecast.get("expected_return_pct", 0.0))
    quality = _finite_number(quality_score)
    agree = _finite_number(agreement)

    if (confidence is None or expected is None or quality is None or agree is None
            or not 0.0 <= confidence <= 1.0
            or not 0.0 <= quality <= 1.0
            or not 0.0 <= agree <= 1.0
            or expected < 0.0):
        return {"approved": False, "status": "NO_TRADE",
                "reason": "invalid_input", "direction": direction,
                "research_only": True, "live_orders": False}

    if direction not in ("UP", "DOWN"):
        return {"approved": False, "status": "NO_TRADE",
                "reason": "forecast_not_directional", "direction": direction,
                "confidence": confidence,
                "research_only": True, "live_orders": False}

    policy = policy_decision(
        confidence, direction, regime=regime, quality_score=quality,
        agreement=agree, leader_follower=leader_follower)
    if not policy["eligible"]:
        return {
            "approved": False, "status": "NO_TRADE", "reason": policy["reason"],
            "direction": direction, "confidence": confidence,
            "policy": policy["policy"], "policy_status": policy["status"],
            "research_only": True, "live_orders": False,
        }

    signed_move = expected if direction == "UP" else -expected
    economics = evaluate_capital_target(
        signed_move, capital_usd=capital_usd, min_profit_usd=min_profit_usd,
        preferred_profit_usd=preferred_profit_usd, exchange=exchange,
        order_type=order_type)
    status = "NO_TRADE"
    if economics.approved:
        status = ("STRONG" if policy["status"] == "STRONG"
                  and economics.tier == "STRONG" else "WATCH")

    return {
        "approved": economics.approved,
        "status": status,
        "direction": direction,
        "confidence": confidence,
        "expected_move_pct": round(signed_move, 4),
        "tier": economics.tier,
        "modeled_profit_usd": economics.modeled_profit_usd,
        "net_move_pct": economics.net_move_pct,
        "round_trip_cost_pct": economics.round_trip_cost_pct,
        "required_move_pct": economics.required_move_pct,
        "preferred_required_move_pct": economics.preferred_required_move_pct,
        "reason": economics.reason,
        "policy_reason": policy["reason"],
        "policy": policy["policy"],
        "policy_status": policy["status"],
        "capital_usd": capital_usd,
        "research_only": True,
        "live_orders": False,
    }
