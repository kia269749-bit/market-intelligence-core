"""Cluster-aware bootstrap utilities for chronological trading outcomes.

Trades on the same UTC day are sampled together. Optional multi-day blocks
preserve short-range dependence between adjacent days. This is a research
interval, not a guarantee of future performance.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from math import ceil
from typing import Iterable


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute percentile of empty sample")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be between 0 and 1")
    index = (len(sorted_values) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(sorted_values) - 1)
    fraction = index - lo
    return sorted_values[lo] * (1.0 - fraction) + sorted_values[hi] * fraction


def daily_block_bootstrap_mean_ci(
    observations: Iterable[tuple[int, float]],
    *,
    confidence: float = 0.90,
    n_resamples: int = 10_000,
    block_days: int = 1,
    seed: int = 20261029,
) -> dict:
    """Percentile CI for mean trade return, resampling contiguous UTC-day blocks.

    Each observation is (timestamp_ms, net_return_pct). Every trade from a
    sampled day is retained together, avoiding the false assumption that
    same-day trades are independent. Missing calendar days remain missing;
    blocks are formed over observed days in chronological order.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if n_resamples < 100:
        raise ValueError("n_resamples must be at least 100")
    if block_days < 1:
        raise ValueError("block_days must be >= 1")
    grouped: dict[str, list[float]] = {}
    for timestamp_ms, value in observations:
        day = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc).date().isoformat()
        number = float(value)
        if not (number == number and abs(number) != float("inf")):
            raise ValueError("returns must be finite")
        grouped.setdefault(day, []).append(number)
    days = sorted(grouped)
    if not days:
        raise ValueError("at least one observation is required")
    if len(days) < 2:
        return {
            "mean_pct": sum(grouped[days[0]]) / len(grouped[days[0]]),
            "ci_low_pct": None,
            "ci_high_pct": None,
            "confidence": confidence,
            "n_trades": len(grouped[days[0]]),
            "n_days": 1,
            "block_days": block_days,
            "resamples": 0,
            "status": "INSUFFICIENT_DAYS",
        }

    blocks = [days[i:i + block_days] for i in range(len(days))]
    rng = random.Random(seed)
    means: list[float] = []
    target_days = len(days)
    for _ in range(n_resamples):
        selected_days: list[str] = []
        while len(selected_days) < target_days:
            start = rng.randrange(len(blocks))
            selected_days.extend(blocks[start])
        selected_days = selected_days[:target_days]
        values = [value for day in selected_days for value in grouped[day]]
        means.append(sum(values) / len(values))
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    all_values = [value for day in days for value in grouped[day]]
    return {
        "mean_pct": sum(all_values) / len(all_values),
        "ci_low_pct": _percentile(means, alpha),
        "ci_high_pct": _percentile(means, 1.0 - alpha),
        "confidence": confidence,
        "n_trades": len(all_values),
        "n_days": len(days),
        "block_days": block_days,
        "resamples": n_resamples,
        "seed": seed,
        "status": "OK",
        "method": "contiguous_utc_day_block_percentile_bootstrap",
    }
