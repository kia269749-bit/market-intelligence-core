from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .fomo_outcome import FomoOutcome, evaluate_fomo_outcome


@dataclass(frozen=True)
class ReplayBar:
    timestamp: int
    price: float


@dataclass(frozen=True)
class HistoricalFomoEvent:
    event_id: str
    trader_id: str
    symbol: str
    timestamp: int
    entry_price: float
    score: float = 0.0
    trader_confidence: float = 0.0
    regime: str = "UNKNOWN"


def replay_fomo_events(
    events: Sequence[HistoricalFomoEvent],
    bars: Sequence[ReplayBar],
    *,
    target_pct: float = 5.0,
    stop_pct: float = -5.0,
    horizon: int | None = None,
    min_future_bars: int = 1,
) -> list[dict]:
    if min_future_bars < 1:
        raise ValueError("min_future_bars must be positive")
    if target_pct <= 0:
        raise ValueError("target_pct must be positive")
    if stop_pct >= 0:
        raise ValueError("stop_pct must be negative")
    if horizon is not None and horizon < 1:
        raise ValueError("horizon must be positive")

    ordered = sorted(bars, key=lambda x: x.timestamp)
    if any(b.timestamp < 0 or b.price <= 0 for b in ordered):
        raise ValueError("bars must have non-negative timestamps and positive prices")
    if any(a.timestamp >= b.timestamp for a, b in zip(ordered, ordered[1:])):
        raise ValueError("bars must have strictly increasing timestamps")

    seen: set[str] = set()
    output: list[dict] = []
    for event in sorted(events, key=lambda x: x.timestamp):
        if not event.event_id:
            raise ValueError("event_id must not be empty")
        if event.event_id in seen:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        seen.add(event.event_id)
        if event.timestamp < 0 or event.entry_price <= 0:
            raise ValueError("event timestamp must be non-negative and entry_price positive")
        if not 0.0 <= event.score <= 1.0:
            raise ValueError("score must be between 0 and 1")
        if not 0.0 <= event.trader_confidence <= 1.0:
            raise ValueError("trader_confidence must be between 0 and 1")

        future = [b for b in ordered if b.timestamp > event.timestamp]
        if len(future) < min_future_bars:
            continue
        prices = [b.price for b in future]
        if horizon is not None:
            prices = prices[:horizon]
        outcome: FomoOutcome = evaluate_fomo_outcome(
            event.entry_price,
            prices,
            target_pct=target_pct,
            stop_pct=stop_pct,
        )
        output.append({
            "event_id": event.event_id,
            "trader_id": event.trader_id,
            "symbol": event.symbol,
            "timestamp": event.timestamp,
            "entry_price": event.entry_price,
            "score": event.score,
            "trader_confidence": event.trader_confidence,
            "regime": event.regime,
            "outcome": outcome,
        })
    return output
