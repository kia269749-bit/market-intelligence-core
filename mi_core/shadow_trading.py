"""Research-only shadow trading ledger with outcome memory."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class ShadowSignal:
    signal_id: str
    timestamp: int
    symbol: str
    side: str
    entry_price: float
    score: float
    regime: str = ""

@dataclass(frozen=True)
class ShadowOutcome:
    signal_id: str
    exit_timestamp: int
    exit_price: float
    return_pct: float
    max_up_pct: float = 0.0
    max_down_pct: float = 0.0

def validate_signal(signal: ShadowSignal) -> None:
    if not signal.signal_id:
        raise ValueError("signal_id must not be empty")
    if signal.timestamp <= 0 or signal.entry_price <= 0:
        raise ValueError("timestamp and entry_price must be positive")
    if signal.side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    if not 0 <= signal.score <= 1:
        raise ValueError("score must be between 0 and 1")

def validate_outcome(outcome: ShadowOutcome) -> None:
    if not outcome.signal_id:
        raise ValueError("signal_id must not be empty")
    if outcome.exit_timestamp <= 0 or outcome.exit_price <= 0:
        raise ValueError("exit_timestamp and exit_price must be positive")

def record_shadow_signals(signals: Iterable[ShadowSignal]) -> list[ShadowSignal]:
    rows = list(signals)
    seen: set[str] = set()
    for signal in rows:
        validate_signal(signal)
        if signal.signal_id in seen:
            raise ValueError(f"duplicate signal_id: {signal.signal_id}")
        seen.add(signal.signal_id)
    return rows

def match_outcomes(signals: Iterable[ShadowSignal], outcomes: Iterable[ShadowOutcome]) -> list[tuple[ShadowSignal, ShadowOutcome]]:
    signal_map = {s.signal_id: s for s in record_shadow_signals(signals)}
    matched = []
    seen = set()
    for outcome in outcomes:
        validate_outcome(outcome)
        if outcome.signal_id in seen:
            raise ValueError(f"duplicate outcome: {outcome.signal_id}")
        signal = signal_map.get(outcome.signal_id)
        if signal is None:
            raise ValueError(f"unknown signal_id: {outcome.signal_id}")
        if outcome.exit_timestamp <= signal.timestamp:
            raise ValueError("outcome must occur after signal")
        seen.add(outcome.signal_id)
        matched.append((signal, outcome))
    return matched

def summarize_outcomes(matches: Iterable[tuple[ShadowSignal, ShadowOutcome]]) -> dict:
    rows = list(matches)
    if not rows:
        return {"count": 0, "win_rate": 0.0, "mean_return": 0.0, "mean_max_up": 0.0, "mean_max_down": 0.0}
    returns = [o.return_pct for _, o in rows]
    return {
        "count": len(rows),
        "win_rate": sum(r > 0 for r in returns) / len(returns),
        "mean_return": sum(returns) / len(returns),
        "mean_max_up": sum(o.max_up_pct for _, o in rows) / len(rows),
        "mean_max_down": sum(o.max_down_pct for _, o in rows) / len(rows),
    }
