"""Stable, dependency-light contracts shared by Project60 specialist brains."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
DIRECTIONS = {"LONG", "SHORT", "NO_TRADE"}
@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    as_of_ms: int
    timeframe: str
    payload: Mapping[str, Any] = field(default_factory=dict)
@dataclass(frozen=True)
class BrainProposal:
    brain_id: str
    family: str
    direction: str
    confidence: float
    as_of_ms: int
    source_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    expected_win_rate: float | None = None
    expected_win_pct: float | None = None
    expected_loss_pct: float | None = None
    available: bool = True
    def __post_init__(self):
        if self.direction not in DIRECTIONS: raise ValueError("invalid direction")
        if not 0.0 <= float(self.confidence) <= 1.0: raise ValueError("confidence must be in [0,1]")
        if self.as_of_ms < 0: raise ValueError("as_of_ms must be non-negative")
@dataclass(frozen=True)
class BrainResult:
    decision: str
    symbol: str
    as_of_ms: int
    confidence: float
    supporting_families: tuple[str, ...] = ()
    weighted_win_rate: float | None = None
    reasons: tuple[str, ...] = ()
    votes: tuple[Mapping[str, Any], ...] = ()
    research_only: bool = True
    live_orders: bool = False
