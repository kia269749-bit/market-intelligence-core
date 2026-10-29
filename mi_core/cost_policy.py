"""Versioned research cost policy; deliberately separate from active v3 behavior."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostPolicy:
    """Round-trip cost assumptions in percentage points, not fractions."""

    base_round_trip_pct: float = 0.15
    strict_round_trip_pct: float = 0.45
    version: str = "v4"

    def __post_init__(self) -> None:
        if self.base_round_trip_pct < 0:
            raise ValueError("base_round_trip_pct must be non-negative")
        if self.strict_round_trip_pct < self.base_round_trip_pct:
            raise ValueError("strict_round_trip_pct must be >= base_round_trip_pct")
        if not self.version.strip():
            raise ValueError("version must be non-empty")

    def cost_usd(self, notional_usd: float, *, strict: bool = False) -> float:
        """Return modeled round-trip cost in USD for the supplied notional."""
        if notional_usd < 0:
            raise ValueError("notional_usd must be non-negative")
        pct = self.strict_round_trip_pct if strict else self.base_round_trip_pct
        return round(float(notional_usd) * pct / 100.0, 10)

    def net_pnl_usd(self, gross_pnl_usd: float, notional_usd: float, *, strict: bool = False) -> float:
        """Subtract the selected round-trip cost from gross PnL."""
        return round(float(gross_pnl_usd) - self.cost_usd(notional_usd, strict=strict), 10)


DEFAULT_COST_POLICY = CostPolicy()
