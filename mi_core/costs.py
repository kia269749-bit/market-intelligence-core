from __future__ import annotations

import math
from dataclasses import dataclass


BASE_ROUND_TRIP_COST_PCT = 0.15
STRICT_ROUND_TRIP_COST_PCT = 0.45


def get_round_trip_cost_pct(policy: str = "base") -> float:
    """Return the centrally defined research round-trip cost policy."""
    if not isinstance(policy, str):
        raise ValueError("policy must be 'base' or 'strict'")
    policies = {
        "base": BASE_ROUND_TRIP_COST_PCT,
        "strict": STRICT_ROUND_TRIP_COST_PCT,
    }
    try:
        return policies[policy.strip().lower()]
    except KeyError:
        raise ValueError("policy must be 'base' or 'strict'") from None


def _finite_number(value: object, name: str, *, positive: bool = False,
                   non_negative: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    if positive and number <= 0:
        raise ValueError(f"{name} must be positive")
    if non_negative and number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number


@dataclass(frozen=True)
class ExecutionCostConfig:
    """Execution assumptions in bps; each value is a full round-trip amount."""

    taker_fee_bps: float = 5.0
    spread_bps: float = 2.0
    slippage_bps: float = 3.0
    impact_bps: float = 1.0

    def __post_init__(self) -> None:
        for name in ("taker_fee_bps", "spread_bps", "slippage_bps", "impact_bps"):
            value = _finite_number(getattr(self, name), name, non_negative=True)
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class ExecutionCost:
    notional: float
    fee: float
    spread: float
    slippage: float
    impact: float
    total: float


def _bps(value: float) -> float:
    return _finite_number(value, "basis points", non_negative=True) / 10_000.0


def estimate_execution_cost(
    notional: float,
    *,
    config: ExecutionCostConfig | None = None,
    spread_bps: float | None = None,
    slippage_bps: float | None = None,
    impact_bps: float | None = None,
    fee_bps: float | None = None,
) -> ExecutionCost:
    """Estimate round-trip execution costs for a trade notional.

    Components are already expressed as full round-trip bps and are summed once.
    This function does not add the separate research-policy percentage.
    fee_bps remains a compatibility override for legacy callers.
    """
    amount = _finite_number(notional, "notional", positive=True)
    if config is not None and not isinstance(config, ExecutionCostConfig):
        raise TypeError("config must be an ExecutionCostConfig")

    cfg = config if config is not None else ExecutionCostConfig()
    fee = cfg.taker_fee_bps if fee_bps is None else _finite_number(
        fee_bps, "fee_bps", non_negative=True
    )
    spread = cfg.spread_bps if spread_bps is None else _finite_number(
        spread_bps, "spread_bps", non_negative=True
    )
    slippage = cfg.slippage_bps if slippage_bps is None else _finite_number(
        slippage_bps, "slippage_bps", non_negative=True
    )
    impact = cfg.impact_bps if impact_bps is None else _finite_number(
        impact_bps, "impact_bps", non_negative=True
    )

    components = {
        "fee": amount * _bps(fee),
        "spread": amount * _bps(spread),
        "slippage": amount * _bps(slippage),
        "impact": amount * _bps(impact),
    }
    total = sum(components.values())
    if not math.isfinite(total):
        raise ValueError("calculated execution cost must be finite")
    return ExecutionCost(
        notional=amount,
        fee=round(components["fee"], 12),
        spread=round(components["spread"], 12),
        slippage=round(components["slippage"], 12),
        impact=round(components["impact"], 12),
        total=round(total, 12),
    )


def apply_cost_to_gross_pnl(gross_pnl: float, cost: ExecutionCost) -> float:
    """Return net PnL after explicitly modeled execution costs."""
    gross = _finite_number(gross_pnl, "gross_pnl")
    if not isinstance(cost, ExecutionCost):
        raise TypeError("cost must be an ExecutionCost")
    total = _finite_number(cost.total, "cost.total", non_negative=True)
    net = gross - total
    if not math.isfinite(net):
        raise ValueError("net PnL must be finite")
    return net
