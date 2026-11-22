"""Optional purged time-series validation adapter.

This is a research evaluator, never a signal generator. It accepts a
precomputed, net-of-cost return series and explicit prediction/evaluation
timestamps. The optional purgedcv dependency is not installed by default.
"""
from __future__ import annotations

import math
from typing import Any


def run_purgedcv_walk_forward(
    returns: Any,
    prediction_times: Any,
    evaluation_times: Any,
    *,
    returns_are_net: bool = False,
    n_splits: int = 5,
    test_size: int | None = None,
    purge_horizon: Any = None,
    embargo: Any = None,
    n_trials: int | None = None,
    var_sharpe: float | None = None,
) -> dict[str, Any]:
    """Evaluate net returns with purged chronological walk-forward splits.

    The caller must provide returns after all applicable fees, spread,
    slippage and impact. evaluation_times must represent the end of each
    sample's label/holding horizon, not merely its prediction timestamp.
    """
    if returns_are_net is not True:
        raise ValueError("returns_are_net=True is required; pass returns after all modeled costs")
    if isinstance(n_splits, bool) or not isinstance(n_splits, int) or n_splits < 1:
        raise ValueError("n_splits must be a positive integer")
    n = len(returns)
    if len(prediction_times) != n or len(evaluation_times) != n:
        raise ValueError("returns, prediction_times and evaluation_times must have equal lengths")
    if test_size is None:
        test_size = max(1, n // (n_splits + 2))
    if isinstance(test_size, bool) or not isinstance(test_size, int) or test_size < 1:
        raise ValueError("test_size must be a positive integer")
    if n_splits * test_size >= n:
        raise ValueError("n_splits * test_size must be smaller than the sample count")
    if (n_trials is None) != (var_sharpe is None):
        raise ValueError("n_trials and var_sharpe must be supplied together")
    if var_sharpe is not None and (not math.isfinite(float(var_sharpe)) or float(var_sharpe) < 0):
        raise ValueError("var_sharpe must be finite and non-negative")

    try:
        import numpy as np
        from purgedcv import (
            WalkForwardSplit,
            deflated_sharpe_ratio_full,
            probabilistic_sharpe_ratio,
        )
    except ImportError:
        return {
            "available": False,
            "reason": "optional_dependency_missing",
            "required_extra": "cloud-validation",
            "research_only": True,
            "live_orders": False,
        }

    values = np.asarray(returns, dtype=float).reshape(-1)
    if values.size != n or not np.isfinite(values).all():
        raise ValueError("returns must be a finite one-dimensional numeric sequence")
    splitter = WalkForwardSplit(
        n_splits=n_splits,
        test_size=test_size,
        prediction_times=prediction_times,
        evaluation_times=evaluation_times,
        purge_horizon=purge_horizon,
        embargo=embargo,
    )

    folds: list[dict[str, Any]] = []
    oos_parts = []
    for fold_number, (train_idx, test_idx) in enumerate(splitter.split(values), start=1):
        fold_returns = values[test_idx]
        if fold_returns.size < 2:
            continue
        fold_std = float(fold_returns.std(ddof=0))
        fold_sharpe = float(fold_returns.mean() / fold_std) if fold_std > 0 else None
        fold_psr = (
            float(probabilistic_sharpe_ratio(fold_returns, benchmark_skill=0.0))
            if fold_std > 0 else None
        )
        folds.append({
            "fold": fold_number,
            "train_samples": int(len(train_idx)),
            "oos_samples": int(len(test_idx)),
            "oos_mean_net_return": float(fold_returns.mean()),
            "oos_sharpe_per_observation": fold_sharpe,
            "psr_vs_zero": fold_psr,
        })
        oos_parts.append(fold_returns)

    if not oos_parts:
        return {
            "available": False,
            "reason": "no_valid_oos_folds",
            "research_only": True,
            "live_orders": False,
        }

    oos = np.concatenate(oos_parts)
    oos_std = float(oos.std(ddof=0))
    result: dict[str, Any] = {
        "available": True,
        "method": "purgedcv.WalkForwardSplit",
        "n_splits": n_splits,
        "test_size": test_size,
        "oos_samples": int(oos.size),
        "oos_mean_net_return": float(oos.mean()),
        "oos_sharpe_per_observation": float(oos.mean() / oos_std) if oos_std > 0 else None,
        "psr_vs_zero": float(probabilistic_sharpe_ratio(oos, benchmark_skill=0.0)) if oos_std > 0 else None,
        "folds": folds,
        "returns_are_net": True,
        "purge_horizon": str(purge_horizon) if purge_horizon is not None else None,
        "embargo": str(embargo) if embargo is not None else None,
        "research_only": True,
        "live_orders": False,
    }
    if n_trials is not None and var_sharpe is not None:
        dsr = deflated_sharpe_ratio_full(oos, n_trials=n_trials, var_sharpe=float(var_sharpe))
        result["dsr"] = float(dsr.dsr)
        result["dsr_benchmark_sharpe"] = float(dsr.sr_star)
        result["n_trials"] = int(n_trials)
    return result
