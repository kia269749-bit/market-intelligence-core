"""Position-size-aware profitability filter.

Research-only: no order placement. A candidate is actionable only when:
1) modeled net target can produce at least min_net_profit_usd,
2) required position size is within max_position_size_usd,
3) modeled loss stays within max_risk_usd,
4) the underlying cost-aware profitability gate already passes.
"""
from __future__ import annotations

from dataclasses import dataclass
from .profitability_gate import GateResult, evaluate_setup


@dataclass(frozen=True)
class USD10Result:
    approved: bool
    reason: str
    gate: GateResult
    min_net_profit_usd: float
    required_position_usd: float
    position_usd: float
    modeled_net_profit_usd: float
    modeled_loss_usd: float
    max_position_usd: float
    max_risk_usd: float


def evaluate_usd10_setup(
    price: float,
    stop: float,
    target: float,
    direction: str,
    confidence: float,
    *,
    min_net_profit_usd: float = 10.0,
    position_size_usd: float | None = None,
    max_position_usd: float = 1000.0,
    max_risk_usd: float = 15.0,
    **cost_kwargs,
) -> USD10Result:
    gate = evaluate_setup(price, stop, target, direction, confidence, **cost_kwargs)
    if gate.net_target_pct <= 0:
        return USD10Result(False, "no_positive_net_edge", gate, min_net_profit_usd, float("inf"),
                           0.0, 0.0, 0.0, max_position_usd, max_risk_usd)

    required = min_net_profit_usd / (gate.net_target_pct / 100.0)
    position = required if position_size_usd is None else float(position_size_usd)

    if not gate.approved:
        reason = "base_profitability_gate_failed"
    elif required > max_position_usd:
        reason = "usd10_requires_too_large_position"
    elif position <= 0 or position > max_position_usd:
        reason = "position_size_outside_limit"
    else:
        modeled_profit = position * gate.net_target_pct / 100.0
        modeled_loss = position * gate.net_risk_pct / 100.0
        if modeled_profit < min_net_profit_usd:
            reason = "net_profit_below_usd10"
        elif modeled_loss > max_risk_usd:
            reason = "risk_budget_exceeded"
        else:
            reason = "usd10_cost_adjusted_passed"

    modeled_profit = position * gate.net_target_pct / 100.0 if position > 0 else 0.0
    modeled_loss = position * gate.net_risk_pct / 100.0 if position > 0 else 0.0
    approved = reason == "usd10_cost_adjusted_passed"
    return USD10Result(
        approved, reason, gate, min_net_profit_usd, round(required, 2),
        round(position, 2), round(modeled_profit, 2), round(modeled_loss, 2),
        max_position_usd, max_risk_usd,
    )
