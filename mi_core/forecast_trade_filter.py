"""Capital-aware filtering for multi-asset forecast candidates.

Research-only. A forecast is never treated as a trade merely because confidence
is high. The filter requires directional agreement, sufficient confidence and
a modeled net profit floor after round-trip costs.
"""
from __future__ import annotations
from .trade_economics import evaluate_capital_target
from .adaptive_signal_policy import policy_decision


def evaluate_forecast(forecast, capital_usd=500.0, min_profit_usd=4.0,
                      preferred_profit_usd=10.0, min_confidence=None,
                      exchange="hyperliquid_perps", order_type="taker",
                      regime="UNKNOWN", quality_score=1.0, agreement=1.0,
                      leader_follower=False, cost_mode="base"):
    if not forecast.get("available"):
        return {"approved": False, "status": "NO_TRADE", "reason": "forecast_unavailable",
                "research_only": True, "live_orders": False}

    direction = forecast.get("direction")
    confidence = float(forecast.get("confidence", 0.0))
    expected = float(forecast.get("expected_return_pct", 0.0))
    if direction not in ("UP", "DOWN"):
        return {"approved": False, "status": "NO_TRADE", "reason": "forecast_not_directional",
                "direction": direction, "confidence": confidence,
                "research_only": True, "live_orders": False}

    # Adaptive thresholds relax modestly in clean trends and tighten in noisy regimes.
    policy = policy_decision(
        confidence, direction, regime=regime, quality_score=quality_score,
        agreement=agreement, leader_follower=leader_follower)
    if not policy["eligible"]:
        return {"approved": False, "status": "NO_TRADE", "reason": policy["reason"],
                "direction": direction, "confidence": confidence,
                "policy": policy["policy"], "policy_status": policy["status"], "research_only": True, "live_orders": False}

    # Prefer the conservative directional interval bound when available.
    # Forecast generation remains separate from economic acceptance.
    lower = forecast.get("lower_return_pct")
    upper = forecast.get("upper_return_pct")
    if lower is not None and upper is not None:
        lower = float(lower)
        upper = float(upper)
        if lower > upper:
            return {"approved": False, "status": "NO_TRADE",
                    "reason": "invalid_forecast_interval", "direction": direction,
                    "research_only": True, "live_orders": False}
        signed_move = lower if direction == "UP" else -upper
        gate_basis = "conservative_forecast_interval_bound"
    else:
        signed_move = expected if direction == "UP" else -expected
        gate_basis = "point_estimate_legacy_fallback"
    economics = evaluate_capital_target(
        signed_move, capital_usd=capital_usd, min_profit_usd=min_profit_usd,
        preferred_profit_usd=preferred_profit_usd, exchange=exchange,
        order_type=order_type, cost_mode=cost_mode)
    status = "NO_TRADE"
    if economics.approved:
        status = "STRONG" if policy["status"] == "STRONG" and economics.tier == "STRONG" else "WATCH"
    return {
        "approved": economics.approved,
        "status": status,
        "direction": direction,
        "confidence": confidence,
        "expected_move_pct": round(signed_move, 4),
        "forecast_point_estimate_pct": round(expected if direction == "UP" else -expected, 4),
        "forecast_gate_basis": gate_basis,
        "forecast_lower_return_pct": lower,
        "forecast_upper_return_pct": upper,
        "tier": economics.tier,
        "modeled_profit_usd": economics.modeled_profit_usd,
        "net_move_pct": economics.net_move_pct,
        "round_trip_cost_pct": economics.round_trip_cost_pct,
        "cost_mode": cost_mode,
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
