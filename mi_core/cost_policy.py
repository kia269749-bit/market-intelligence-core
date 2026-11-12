"""Single source of truth for research round-trip execution costs.

Rates are percentage points of notional (0.12 means 0.12%, not 12%).
All project research/evaluation paths use one Taker round-trip assumption.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CostPolicy:
    """Versioned round-trip costs in percentage points."""

    base_round_trip_pct: float = 0.12
    version: str = "v6-taker-0.12"

    def __post_init__(self) -> None:
        base = float(self.base_round_trip_pct)
        if not math.isfinite(base) or base != 0.12:
            raise ValueError("the project Taker round-trip cost is fixed at 0.12%")
        if not self.version.strip():
            raise ValueError("version must be non-empty")

    def round_trip_pct(self, mode: str = "base") -> float:
        selected = str(mode).strip().lower()
        if selected == "base":
            return float(self.base_round_trip_pct)
        raise ValueError("cost mode must be 'base'")

    def cost_usd(self, notional_usd: float, *, mode: str = "base") -> float:
        notional = float(notional_usd)
        if not math.isfinite(notional) or notional < 0:
            raise ValueError("notional_usd must be finite and non-negative")
        return round(notional * self.round_trip_pct(mode) / 100.0, 10)

    def net_pnl_usd(self, gross_pnl_usd: float, notional_usd: float, *, mode: str = "base") -> float:
        gross = float(gross_pnl_usd)
        if not math.isfinite(gross):
            raise ValueError("gross_pnl_usd must be finite")
        return round(gross - self.cost_usd(notional_usd, mode=mode), 10)


BASE_ROUND_TRIP_COST_PCT = 0.12
DEFAULT_COST_POLICY = CostPolicy(base_round_trip_pct=BASE_ROUND_TRIP_COST_PCT)


def get_round_trip_cost_pct(mode: str = "base", policy: CostPolicy = DEFAULT_COST_POLICY) -> float:
    """Resolve the single configured Taker round-trip rate."""
    return policy.round_trip_pct(mode)


def resolve_round_trip_cost_pct(
    mode: str = "base",
    policy: CostPolicy = DEFAULT_COST_POLICY,
    override: float | None = None,
) -> float:
    """Resolve the single configured Taker rate; overrides must match policy."""
    value = get_round_trip_cost_pct(mode, policy) if override is None else float(override)
    if not math.isfinite(value) or value != policy.base_round_trip_pct:
        raise ValueError("project round_trip_cost_pct is fixed at 0.12%; alternate rates are retired")
    return value
