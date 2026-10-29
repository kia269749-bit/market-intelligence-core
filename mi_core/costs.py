from __future__ import annotations

from dataclasses import dataclass


# Project-wide research assumption: full round-trip cost as a percentage of notional.
ROUND_TRIP_COST_PCT = 0.15


@dataclass(frozen=True)
class ExecutionCostConfig:
    """Diagnostic component assumptions, expressed in basis points.

    These components are a separate decomposed estimate and are not the
    project's fixed aggregate ROUND_TRIP_COST_PCT. Do not treat their default
    sum (11 bps) as a replacement for the 24 bps project policy.
    """

    taker_fee_bps: float = 5.0
    spread_bps: float = 2.0
    slippage_bps: float = 3.0
    impact_bps: float = 1.0

    def __post_init__(self) -> None:
        for name in ("taker_fee_bps", "spread_bps", "slippage_bps", "impact_bps"):
            value = float(getattr(self, name))
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class ExecutionCost:
    notional: float
    fee: float
    spread: float
    slippage: float
    impact: float
    total: float


def _bps(value: float) -> float:
    return float(value) / 10_000.0


def estimate_execution_cost(
    notional: float,
    *,
    config: ExecutionCostConfig | None = None,
    spread_bps: float | None = None,
    slippage_bps: float | None = None,
    impact_bps: float | None = None,
    fee_bps: float | None = None,
) -> ExecutionCost:
    """Estimate the decomposed diagnostic cost for a trade notional.

    This function sums the explicitly supplied component assumptions. Its
    default 11 bps component estimate is intentionally distinct from the
    project's fixed aggregate ROUND_TRIP_COST_PCT (15 bps). fee_bps, when
    supplied, is a compatibility override for the taker fee used by the legacy
    backtest. Use ROUND_TRIP_COST_PCT for fixed-policy net-return validation.
    """

    if notional <= 0:
        raise ValueError("notional must be positive")

    cfg = config or ExecutionCostConfig()
    fee = cfg.taker_fee_bps if fee_bps is None else float(fee_bps)
    spread = cfg.spread_bps if spread_bps is None else float(spread_bps)
    slippage = cfg.slippage_bps if slippage_bps is None else float(slippage_bps)
    impact = cfg.impact_bps if impact_bps is None else float(impact_bps)

    values = {
        "fee_bps": fee,
        "spread_bps": spread,
        "slippage_bps": slippage,
        "impact_bps": impact,
    }
    if any(v < 0 for v in values.values()):
        raise ValueError("cost assumptions must be non-negative")

    components = {
        "fee": notional * _bps(fee),
        "spread": notional * _bps(spread),
        "slippage": notional * _bps(slippage),
        "impact": notional * _bps(impact),
    }
    total = sum(components.values())
    return ExecutionCost(
        notional=float(notional),
        fee=round(components["fee"], 12),
        spread=round(components["spread"], 12),
        slippage=round(components["slippage"], 12),
        impact=round(components["impact"], 12),
        total=round(total, 12),
    )


def apply_cost_to_gross_pnl(gross_pnl: float, cost: ExecutionCost) -> float:
    """Return net PnL after explicitly modeled execution costs."""

    return float(gross_pnl) - cost.total
