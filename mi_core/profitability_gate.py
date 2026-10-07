"""Cost-aware research gate for candidate signals.

No order execution. The gate models fees, spread and slippage and rejects
setups that do not clear a minimum net edge and risk/reward threshold.
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

def evaluate_setup(price: float, stop: float, target: float, direction: str,
                   confidence: float, fee_bps: float = 10.0,
                   spread_bps: float = 5.0, slippage_bps: float = 8.0,
                   min_confidence: float = 0.70, min_rr: float = 1.50,
                   min_net_edge_pct: float = 0.50) -> GateResult:
    d=str(direction).upper()
    valid = price > 0 and stop > 0 and target > 0 and (
        (d == "BULLISH" and stop < price < target) or
        (d == "BEARISH" and target < price < stop)
    )
    if not valid:
        return GateResult(False, "invalid_price_levels", 0, 0, 0, 0, 0, 0)
    gross_target=((target/price)-1)*100 if d=="BULLISH" else ((price/target)-1)*100
    gross_stop=((price/stop)-1)*100 if d=="BULLISH" else ((stop/price)-1)*100
    cost=2*(fee_bps+spread_bps+slippage_bps)/100
    net_target=gross_target-cost
    net_risk=gross_stop+cost
    rr=net_target/net_risk if net_risk>0 else 0
    if confidence < min_confidence:
        reason="confidence_below_gate"
    elif net_target < min_net_edge_pct:
        reason="edge_too_small_after_costs"
    elif rr < min_rr:
        reason="risk_reward_below_gate"
    else:
        reason="cost_adjusted_edge_passed"
    return GateResult(reason=="cost_adjusted_edge_passed",reason,
                      round(gross_target,4),round(gross_stop,4),round(cost,4),
                      round(net_target,4),round(net_risk,4),round(rr,4))

def evaluate_buy(price, stop, target, confidence, **kwargs):
    return evaluate_setup(price,stop,target,"BULLISH",confidence,**kwargs)

def evaluate_sell(price, stop, target, confidence, **kwargs):
    return evaluate_setup(price,stop,target,"BEARISH",confidence,**kwargs)
