"""Single source of truth for research round-trip execution costs.

Rates are percentage points of notional (0.15 means 0.15%, not 15%).
The active v3 coordinator may explicitly retain its legacy component model;
new v4 research/evaluation paths use this policy by default.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CostPolicy:
    """Versioned round-trip costs in percentage points."""

    base_round_trip_pct: float = 0.15
    strict_round_trip_pct: float = 0.15
    version: str = "v5-taker-0.15"

    def __post_init__(self) -> None:
        base = float(self.base_round_trip_pct)
        strict = float(self.strict_round_trip_pct)
        if not math.isfinite(base) or base < 0:
            raise ValueError("base_round_trip_pct must be finite and non-negative")
        if not math.isfinite(strict) or strict < base:
            raise ValueError("strict_round_trip_pct must be finite and >= base_round_trip_pct")
        if not self.version.strip():
            raise ValueError("version must be non-empty")

    def round_trip_pct(self, mode: str = "base") -> float:
        selected = str(mode).strip().lower()
        if selected == "base":
            return float(self.base_round_trip_pct)
        if selected == "strict":
            return float(self.strict_round_trip_pct)
        raise ValueError("cost mode must be 'base' or 'strict'")

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


BASE_ROUND_TRIP_COST_PCT = 0.15
STRICT_ROUND_TRIP_COST_PCT = 0.15
DEFAULT_COST_POLICY = CostPolicy(
    base_round_trip_pct=BASE_ROUND_TRIP_COST_PCT,
    strict_round_trip_pct=STRICT_ROUND_TRIP_COST_PCT,
)


def get_round_trip_cost_pct(mode: str = "base", policy: CostPolicy = DEFAULT_COST_POLICY) -> float:
    """Resolve the single configured Taker round-trip rate; legacy mode names resolve identically."""
    return policy.round_trip_pct(mode)


def resolve_round_trip_cost_pct(
    mode: str = "base",
    policy: CostPolicy = DEFAULT_COST_POLICY,
    override: float | None = None,
) -> float:
    """Resolve a policy rate, allowing an explicit legacy/scenario override."""
    value = get_round_trip_cost_pct(mode, policy) if override is None else float(override)
    if not math.isfinite(value) or value < 0:
        raise ValueError("round_trip_cost_pct must be finite and non-negative")
    return value
