"""Cost-aware research gate for candidate signals.

This module never places orders. It rejects setups whose modeled edge is too
small after fees, spread, and slippage. It is a safety/validation gate, not a
profit guarantee.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class GateResult:
    approved: bool
    reason: str
    gross_target_pct: float
    gross_stop_pct: float
    round_trip_cost_pct: float
    net_target_pct: float
    net_risk_pct: float
    net_rr: float

def evaluate_buy(price: float, stop: float, target: float, confidence: float,
                 fee_bps: float = 10.0, spread_bps: float = 5.0,
                 slippage_bps: float = 8.0, min_confidence: float = 0.70,
                 min_rr: float = 1.50, min_net_edge_pct: float = 0.50) -> GateResult:
    if price <= 0 or stop <= 0 or target <= price:
        return GateResult(False, "invalid_price_levels", 0, 0, 0, 0, 0, 0)
    gross_target = (target / price - 1.0) * 100.0
    gross_stop = (1.0 - stop / price) * 100.0
    cost = 2.0 * (fee_bps + spread_bps + slippage_bps) / 100.0
    net_target = gross_target - cost
    net_risk = gross_stop + cost
    rr = net_target / net_risk if net_risk > 0 else 0.0
    if confidence < min_confidence:
        reason = "confidence_below_gate"
        approved = False
    elif net_target < min_net_edge_pct:
        reason = "edge_too_small_after_costs"
        approved = False
    elif rr < min_rr:
        reason = "risk_reward_below_gate"
        approved = False
    else:
        reason = "cost_adjusted_edge_passed"
        approved = True
    return GateResult(approved, reason, round(gross_target,4), round(gross_stop,4),
                      round(cost,4), round(net_target,4), round(net_risk,4), round(rr,4))
