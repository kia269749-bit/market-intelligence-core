"""Cluster-aware bootstrap utilities for chronological trading outcomes.

Trades on the same UTC day are sampled together. Multi-day blocks are built
on the complete UTC calendar, including dates with no trades. This is a
research interval, not a guarantee of future performance.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
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
    """Percentile CI for mean trade return using contiguous UTC calendar blocks.

    Each observation is (timestamp_ms, net_return_pct). Trades on a sampled
    date stay clustered. The sampling timeline includes every calendar date
    between the first and last observation, even dates with no trades.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if n_resamples < 100:
        raise ValueError("n_resamples must be at least 100")
    if block_days < 1:
        raise ValueError("block_days must be >= 1")

    grouped: dict[date, list[float]] = {}
    for timestamp_ms, value in observations:
        day = datetime.fromtimestamp(
            int(timestamp_ms) / 1000, tz=timezone.utc
        ).date()
        number = float(value)
        if not (number == number and abs(number) != float("inf")):
            raise ValueError("returns must be finite")
        grouped.setdefault(day, []).append(number)

    if not grouped:
        raise ValueError("at least one observation is required")

    active_days = sorted(grouped)
    all_values = [value for day in active_days for value in grouped[day]]
    observed_mean = sum(all_values) / len(all_values)
    calendar_days = [
        active_days[0] + timedelta(days=i)
        for i in range((active_days[-1] - active_days[0]).days + 1)
    ]

    if len(active_days) < 2:
        return {
            "mean_pct": observed_mean,
            "ci_low_pct": None,
            "ci_high_pct": None,
            "confidence": confidence,
            "n_trades": len(all_values),
            "n_days": len(active_days),
            "n_calendar_days": len(calendar_days),
            "block_days": block_days,
            "effective_block_days": min(block_days, len(calendar_days)),
            "resamples": 0,
            "status": "INSUFFICIENT_DAYS",
        }

    effective_block_days = min(block_days, len(calendar_days))
    # Fixed-length moving blocks over the real calendar. Empty dates remain
    # in the timeline and therefore cannot make separated active days adjacent.
    blocks = [
        calendar_days[i:i + effective_block_days]
        for i in range(len(calendar_days) - effective_block_days + 1)
    ]
    rng = random.Random(seed)
    means: list[float] = []
    target_calendar_days = len(calendar_days)
    attempts = 0
    max_attempts = n_resamples * 100

    while len(means) < n_resamples and attempts < max_attempts:
        attempts += 1
        selected_days: list[date] = []
        while len(selected_days) < target_calendar_days:
            selected_days.extend(blocks[rng.randrange(len(blocks))])
        selected_days = selected_days[:target_calendar_days]
        values = [
            value
            for day in selected_days
            for value in grouped.get(day, ())
        ]
        # A replicate with no trades has no defined mean trade return.
        if values:
            means.append(sum(values) / len(values))

    if len(means) != n_resamples:
        raise ValueError(
            "could not generate enough non-empty bootstrap replicates; "
            "calendar coverage is too sparse for this block length"
        )

    means.sort()
    alpha = (1.0 - confidence) / 2.0
    return {
        "mean_pct": observed_mean,
        "ci_low_pct": _percentile(means, alpha),
        "ci_high_pct": _percentile(means, 1.0 - alpha),
        "confidence": confidence,
        "n_trades": len(all_values),
        "n_days": len(active_days),
        "n_calendar_days": len(calendar_days),
        "block_days": block_days,
        "effective_block_days": effective_block_days,
        "resamples": n_resamples,
        "seed": seed,
        "status": "OK",
        "method": "contiguous_utc_calendar_day_block_percentile_bootstrap",
    }
