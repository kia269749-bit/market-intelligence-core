"""Research-only time alignment between economic observations and crypto bars.

Only information published on or before a crypto bar timestamp may be used.
No future observation is ever selected.
"""
from __future__ import annotations
from dataclasses import dataclass
from bisect import bisect_right

@dataclass(frozen=True)
class TimestampedMacro:
    ts: int
    value: float
    source: str = ""

def align_previous(bar_timestamps: list[int], observations: list[TimestampedMacro],
                   max_age_seconds: int | None = None) -> list[TimestampedMacro | None]:
    if max_age_seconds is not None and max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    ordered = sorted(observations, key=lambda x: x.ts)
    times = [x.ts for x in ordered]
    out = []
    for bar_ts in bar_timestamps:
        idx = bisect_right(times, bar_ts) - 1
        if idx < 0:
            out.append(None)
            continue
        obs = ordered[idx]
        if max_age_seconds is not None and bar_ts - obs.ts > max_age_seconds:
            out.append(None)
        else:
            out.append(obs)
    return out

def normalize_returns(values: list[float]) -> list[float]:
    if not values:
        return []
    out = [0.0]
    for previous, current in zip(values, values[1:]):
        if previous == 0:
            out.append(0.0)
        else:
            out.append(current / previous - 1.0)
    return out
