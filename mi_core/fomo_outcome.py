from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class FomoOutcome:
    horizon: int
    return_pct: float
    max_up_pct: float
    max_down_pct: float
    hit_target: bool
    hit_stop: bool


def _pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (float(end) / float(start) - 1.0) * 100.0


def evaluate_fomo_outcome(
    entry_price: float,
    future_prices: Sequence[float],
    *,
    horizon: int | None = None,
    target_pct: float = 5.0,
    stop_pct: float = -5.0,
) -> FomoOutcome:
    if not future_prices:
        raise ValueError("future_prices must not be empty")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")

    prices = [float(p) for p in future_prices]
    if any(p <= 0 for p in prices):
        raise ValueError("future_prices must be positive")

    if horizon is not None:
        if horizon < 1:
            raise ValueError("horizon must be positive")
        prices = prices[:horizon]
        if not prices:
            raise ValueError("horizon exceeds available future_prices")

    returns = [_pct(entry_price, p) for p in prices]
    final_return = returns[-1]
    max_up = max(returns)
    max_down = min(returns)

    return FomoOutcome(
        horizon=len(prices),
        return_pct=round(final_return, 6),
        max_up_pct=round(max_up, 6),
        max_down_pct=round(max_down, 6),
        hit_target=max_up >= target_pct,
        hit_stop=max_down <= stop_pct,
    )


def summarize_fomo_outcomes(outcomes: Sequence[FomoOutcome]) -> dict:
    if not outcomes:
        return {
            "events": 0,
            "mean_return_pct": 0.0,
            "median_return_pct": 0.0,
            "hit_target_rate": 0.0,
            "hit_stop_rate": 0.0,
            "positive_return_rate": 0.0,
        }

    returns = sorted(o.return_pct for o in outcomes)
    n = len(returns)
    median = returns[n // 2] if n % 2 else (returns[n // 2 - 1] + returns[n // 2]) / 2.0
    return {
        "events": n,
        "mean_return_pct": round(sum(returns) / n, 6),
        "median_return_pct": round(median, 6),
        "hit_target_rate": round(sum(o.hit_target for o in outcomes) / n, 6),
        "hit_stop_rate": round(sum(o.hit_stop for o in outcomes) / n, 6),
        "positive_return_rate": round(sum(o.return_pct > 0 for o in outcomes) / n, 6),
    }
