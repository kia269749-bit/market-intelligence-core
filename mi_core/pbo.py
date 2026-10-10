"""Combinatorially symmetric cross-validation for strategy-selection overfit checks.

This is a research diagnostic, not a profitability guarantee. Input must contain
aligned, per-period net returns for every strategy, after realistic costs.
"""
from __future__ import annotations

from itertools import combinations
from math import comb, isfinite
from statistics import mean, stdev
from typing import Mapping, Sequence


def _sharpe(values: Sequence[float]) -> float:
    avg = mean(values)
    if len(values) < 2:
        return 0.0
    vol = stdev(values)
    if vol == 0:
        # A zero-volatility Sharpe is undefined; keep reports valid JSON.
        return 0.0
    return avg / vol


def estimate_pbo_cscv(
    returns_by_strategy: Mapping[str, Sequence[float]],
    *,
    n_blocks: int = 8,
) -> dict:
    """Estimate PBO using equal contiguous blocks and symmetric half-splits.

    For each choice of half the blocks as in-sample, select the strategy with
    the best in-sample Sharpe, then measure its OOS Sharpe percentile among all
    supplied strategies. PBO is the fraction of splits where that selected
    strategy ranks below the OOS median.

    Returns a JSON-serializable summary plus per-split diagnostics.
    """
    if len(returns_by_strategy) < 2:
        raise ValueError("at least two candidate strategies are required")
    if n_blocks < 4 or n_blocks % 2:
        raise ValueError("n_blocks must be an even integer >= 4")

    names = list(returns_by_strategy)
    series = [list(map(float, returns_by_strategy[name])) for name in names]
    lengths = {len(row) for row in series}
    if len(lengths) != 1:
        raise ValueError("all strategy return series must have equal lengths")
    n_obs = lengths.pop()
    if n_obs < n_blocks or n_obs % n_blocks:
        raise ValueError("observations must be >= n_blocks and divisible by n_blocks")
    if any(not isfinite(value) for row in series for value in row):
        raise ValueError("returns must all be finite numbers")

    block_size = n_obs // n_blocks
    blocks = [
        (start, start + block_size)
        for start in range(0, n_obs, block_size)
    ]
    half = n_blocks // 2
    split_rows = []
    overfit_count = 0

    for is_blocks in combinations(range(n_blocks), half):
        is_set = set(is_blocks)
        oos_blocks = [i for i in range(n_blocks) if i not in is_set]

        def gather(row: Sequence[float], indices: Sequence[int]) -> list[float]:
            values = []
            for idx in indices:
                start, end = blocks[idx]
                values.extend(row[start:end])
            return values

        is_scores = [_sharpe(gather(row, is_blocks)) for row in series]
        # Deterministic tie-break by input order; ties are still reflected in OOS ranking.
        selected_idx = max(range(len(names)), key=lambda idx: (is_scores[idx], -idx))
        oos_scores = [_sharpe(gather(row, oos_blocks)) for row in series]
        selected_score = oos_scores[selected_idx]
        less = sum(score < selected_score for score in oos_scores)
        equal = sum(score == selected_score for score in oos_scores)
        percentile = (less + 0.5 * equal) / len(oos_scores)
        below_median = percentile < 0.5
        overfit_count += int(below_median)
        split_rows.append({
            "is_blocks": list(is_blocks),
            "selected_strategy": names[selected_idx],
            "selected_is_sharpe": is_scores[selected_idx],
            "selected_oos_sharpe": selected_score,
            "selected_oos_percentile": percentile,
            "below_oos_median": below_median,
        })

    total = len(split_rows)
    return {
        "method": "CSCV",
        "metric": "sharpe",
        "n_strategies": len(names),
        "n_observations": n_obs,
        "n_blocks": n_blocks,
        "splits": total,
        "overfit_splits": overfit_count,
        "pbo": overfit_count / total if total else 0.0,
        "research_only": True,
        "live_orders": False,
        "split_results": split_rows,
        "limitations": [
            "PBO diagnoses selection overfit among supplied candidates; it does not prove future profitability.",
            "Input returns must be point-in-time aligned and net of fees, spread, slippage, and funding where applicable.",
            "CSCV is not a substitute for a final untouched chronological holdout or realistic execution simulation.",
        ],
    }
