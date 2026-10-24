"""Research-only block-bootstrap robustness checks for realized trade outcomes.

This module consumes already-computed net trade P&L. It does not fetch market
data, estimate costs, create signals, or place orders. Costs must be applied
upstream exactly once before these outcomes are passed in.
"""
from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from typing import Any


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute quantile from an empty sample")
    index = min(len(ordered) - 1, max(0, int(q * len(ordered))))
    return ordered[index]


def _trade_pnl(trades: Sequence[Mapping[str, Any] | float | int]) -> list[float]:
    values: list[float] = []
    for index, trade in enumerate(trades):
        raw = trade.get("net_pnl_usd") if isinstance(trade, Mapping) else trade
        if raw is None or isinstance(raw, bool):
            raise ValueError(f"trade {index} must provide finite net_pnl_usd")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"trade {index} must provide finite net_pnl_usd") from exc
        if not math.isfinite(value):
            raise ValueError(f"trade {index} net_pnl_usd must be finite")
        values.append(value)
    return values


def run_trade_bootstrap(
    trades: Sequence[Mapping[str, Any] | float | int],
    *,
    simulations: int = 5000,
    block_size: int = 1,
    seed: int = 19,
    initial_equity_usd: float = 500.0,
) -> dict[str, Any]:
    """Bootstrap net trade outcomes to test result fragility.

    Uses a circular moving-block bootstrap over the supplied chronological
    trades. block_size=1 is ordinary resampling; larger blocks preserve some
    short-range ordering/dependence. Each simulation resamples exactly N
    outcomes for N observed trades. It reports the distribution of total net
    P&L, mean net P&L per trade, and peak-to-trough drawdown.

    This is a robustness diagnostic, not a forecast. It cannot model unseen
    regimes, market impact, funding, gaps, or execution errors absent from the
    supplied outcomes. Pass already-net outcomes so execution costs are not
    silently omitted or charged twice.
    """
    pnl = _trade_pnl(trades)
    if not pnl:
        raise ValueError("at least one trade outcome is required")
    if isinstance(simulations, bool) or not isinstance(simulations, int) or not 100 <= simulations <= 100_000:
        raise ValueError("simulations must be an integer between 100 and 100000")
    if isinstance(block_size, bool) or not isinstance(block_size, int) or not 1 <= block_size <= len(pnl):
        raise ValueError("block_size must be an integer between 1 and the trade count")
    if isinstance(initial_equity_usd, bool):
        raise ValueError("initial_equity_usd must be finite and positive")
    try:
        initial_equity = float(initial_equity_usd)
    except (TypeError, ValueError) as exc:
        raise ValueError("initial_equity_usd must be finite and positive") from exc
    if not math.isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("initial_equity_usd must be finite and positive")

    rng = random.Random(seed)
    count = len(pnl)
    totals: list[float] = []
    expectancies: list[float] = []
    drawdowns: list[float] = []
    positive = 0

    for _ in range(simulations):
        sample: list[float] = []
        while len(sample) < count:
            start = rng.randrange(count)
            take = min(block_size, count - len(sample))
            sample.extend(pnl[(start + offset) % count] for offset in range(take))
        equity = initial_equity
        peak = equity
        max_drawdown = 0.0
        total = 0.0
        for value in sample:
            total += value
            equity += value
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        totals.append(total)
        expectancies.append(total / count)
        drawdowns.append(max_drawdown)
        if total > 0:
            positive += 1

    observed_total = sum(pnl)
    return {
        "status": "OK",
        "trade_count": count,
        "simulations": simulations,
        "block_size": block_size,
        "seed": seed,
        "observed_net_pnl_usd": round(observed_total, 8),
        "observed_expectancy_usd": round(observed_total / count, 8),
        "probability_positive_net_pct": round(100.0 * positive / simulations, 4),
        "net_pnl_p05_usd": round(_quantile(totals, 0.05), 8),
        "net_pnl_median_usd": round(_quantile(totals, 0.50), 8),
        "net_pnl_p95_usd": round(_quantile(totals, 0.95), 8),
        "expectancy_ci95_low_usd": round(_quantile(expectancies, 0.025), 8),
        "expectancy_ci95_high_usd": round(_quantile(expectancies, 0.975), 8),
        "max_drawdown_p95_usd": round(_quantile(drawdowns, 0.95), 8),
        "max_drawdown_p95_pct_initial_equity": round(100.0 * _quantile(drawdowns, 0.95) / initial_equity, 6),
        "research_only": True,
        "live_orders": False,
        "note": "Bootstrap sensitivity only; not a profitability guarantee or a substitute for chronological walk-forward/OOS validation.",
    }
