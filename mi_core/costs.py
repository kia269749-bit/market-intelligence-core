from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ExecutionCostConfig:
    """Research-only execution-cost assumptions, expressed in basis points."""

    taker_fee_bps: float = 6.0
    spread_bps: float = 2.0
    slippage_bps: float = 3.0
    impact_bps: float = 1.0

    def __post_init__(self) -> None:
        for name in ("taker_fee_bps", "spread_bps", "slippage_bps", "impact_bps"):
            raw = getattr(self, name)
            if isinstance(raw, bool):
                raise ValueError(f"{name} must be finite and non-negative")
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be finite and non-negative") from exc
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
            # Normalize accepted numeric strings to floats in the frozen object.
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
    """Estimate round-trip execution costs for a trade notional.

    The estimate deliberately keeps each cost component separate so validation
    can report where profitability is being consumed. fee_bps, when supplied,
    is a compatibility override for the taker fee used by the legacy backtest.
    When config is omitted, all assumptions are loaded from central_config.
    """

    if isinstance(notional, bool):
        raise ValueError("notional must be finite and positive")
    try:
        notional_value = float(notional)
    except (TypeError, ValueError) as exc:
        raise ValueError("notional must be finite and positive") from exc
    if not isfinite(notional_value) or notional_value <= 0:
        raise ValueError("notional must be finite and positive")

    if config is None:
        from .central_config import load_settings
        settings = load_settings()
        cfg = ExecutionCostConfig(
            taker_fee_bps=settings.taker_fee_bps,
            spread_bps=settings.spread_bps,
            slippage_bps=settings.slippage_bps,
            impact_bps=settings.impact_bps,
        )
    else:
        cfg = config
    overrides = {"fee_bps": fee_bps, "spread_bps": spread_bps,
                 "slippage_bps": slippage_bps, "impact_bps": impact_bps}
    for name, value in overrides.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be finite and non-negative")
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
    if any(not isfinite(v) or v < 0 for v in values.values()):
        raise ValueError("cost assumptions must be finite and non-negative")

    # Each input is a per-side assumption. A round trip pays entry and exit
    # friction; spread is modeled per side here for conservative consistency.
    components = {
        "fee": notional_value * _bps(fee) * 2.0,
        "spread": notional_value * _bps(spread) * 2.0,
        "slippage": notional_value * _bps(slippage) * 2.0,
        "impact": notional_value * _bps(impact) * 2.0,
    }
    total = sum(components.values())
    return ExecutionCost(
        notional=notional_value,
        fee=round(components["fee"], 12),
        spread=round(components["spread"], 12),
        slippage=round(components["slippage"], 12),
        impact=round(components["impact"], 12),
        total=round(total, 12),
    )


def apply_cost_to_gross_pnl(gross_pnl: float, cost: ExecutionCost) -> float:
    """Return net PnL after explicitly modeled execution costs."""

    return float(gross_pnl) - cost.total
