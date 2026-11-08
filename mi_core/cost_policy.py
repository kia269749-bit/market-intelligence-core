"""Single source of truth for research round-trip cost scenarios.

Rates are percentage points of notional: 0.15 means 0.15%, not 15%.
These fixed v4 scenarios are separate from the legacy itemized bps estimator.
Do not add the itemized estimate to either fixed scenario.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CostPolicy:
    base_round_trip_pct: float = 0.15
    strict_round_trip_pct: float = 0.45
    version: str = "v4"

    def __post_init__(self) -> None:
        base = float(self.base_round_trip_pct)
        strict = float(self.strict_round_trip_pct)
        if not math.isfinite(base) or base < 0:
            raise ValueError("base_round_trip_pct must be finite and non-negative")
        if not math.isfinite(strict) or strict < base:
            raise ValueError("strict_round_trip_pct must be finite and >= base")
        if not self.version.strip():
            raise ValueError("version must be non-empty")

    def round_trip_pct(self, mode: str = "base") -> float:
        mode = str(mode).strip().lower()
        if mode == "base":
            return float(self.base_round_trip_pct)
        if mode == "strict":
            return float(self.strict_round_trip_pct)
        raise ValueError("cost mode must be 'base' or 'strict'")


DEFAULT_COST_POLICY = CostPolicy()


def resolve_round_trip_cost_pct(
    mode: str = "base",
    policy: CostPolicy = DEFAULT_COST_POLICY,
    override: float | None = None,
) -> float:
    value = policy.round_trip_pct(mode) if override is None else float(override)
    if not math.isfinite(value) or value < 0:
        raise ValueError("round_trip_cost_pct must be finite and non-negative")
    return value
