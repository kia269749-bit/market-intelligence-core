"""Historical replay of point-in-time macro context alongside crypto bars.

The replay is intentionally deterministic: macro observations are selected only
from timestamps at or before each crypto bar, and stale observations can be
excluded. No network access occurs here.
"""
from __future__ import annotations
from dataclasses import dataclass
from .macro_alignment import TimestampedMacro, align_previous
from .cross_asset import CrossAssetSnapshot, cross_asset_regime

@dataclass(frozen=True)
class MacroReplayRow:
    ts: int
    macro: CrossAssetSnapshot | None
    regime: str | None
    stale: bool

def replay_macro_context(
    crypto_timestamps: list[int],
    crypto_returns: list[float],
    dollar: list[TimestampedMacro],
    gold: list[TimestampedMacro],
    equity: list[TimestampedMacro],
    volatility: list[TimestampedMacro],
    max_age_seconds: int | None = None,
) -> list[MacroReplayRow]:
    if len(crypto_timestamps) != len(crypto_returns):
        raise ValueError("crypto_timestamps and crypto_returns must have equal length")
    streams = [dollar, gold, equity, volatility]
    aligned = [align_previous(crypto_timestamps, stream, max_age_seconds) for stream in streams]
    rows = []
    for i, ts in enumerate(crypto_timestamps):
        values = [stream[i] for stream in aligned]
        if any(x is None for x in values):
            rows.append(MacroReplayRow(ts, None, None, True))
            continue
        snap = CrossAssetSnapshot(
            crypto_return=float(crypto_returns[i]),
            dollar_return=float(values[0].value),
            gold_return=float(values[1].value),
            equity_return=float(values[2].value),
            volatility_return=float(values[3].value),
        )
        rows.append(MacroReplayRow(ts, snap, cross_asset_regime(snap)["regime"], False))
    return rows
