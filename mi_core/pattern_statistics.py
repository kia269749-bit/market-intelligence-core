"""Statistical diagnostics for exploratory pattern studies.

Moving-block bootstrap preserves short-range dependence better than iid
resampling. These diagnostics are not proof of a tradable edge; they require
enough independent observations and must be interpreted with the frozen split.
"""
from __future__ import annotations

from math import isfinite
from random import Random
from typing import Iterable, Sequence


def _values(values: Iterable[float], label: str) -> list[float]:
    try:
        raw_values = list(values)
        if any(isinstance(value, bool) for value in raw_values):
            raise ValueError(f"{label} must contain finite numbers")
        result = [float(value) for value in raw_values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain finite numbers") from exc
    if any(not isfinite(value) for value in result):
        raise ValueError(f"{label} must contain finite numbers")
    return result


def _block_sample(values: Sequence[float], size: int, rng: Random) -> list[float]:
    """Circular moving-block sample of exactly len(values) observations."""
    n = len(values)
    sampled: list[float] = []
    while len(sampled) < n:
        start = rng.randrange(n)
        sampled.extend(values[(start + offset) % n] for offset in range(size))
    return sampled[:n]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _validate_sampling(reps: int, block_size: int) -> None:
    if isinstance(reps, bool) or not isinstance(reps, int) or reps < 100:
        raise ValueError("reps must be an integer >= 100")
    if isinstance(block_size, bool) or not isinstance(block_size, int) or block_size < 1:
        raise ValueError("block_size must be an integer >= 1")


def bootstrap_mean_ci(
    returns: Iterable[float], *, reps: int = 4000, block_size: int = 3,
    confidence: float = 0.95, seed: int = 20261024,
) -> dict:
    values = _values(returns, "returns")
    _validate_sampling(reps, block_size)
    if isinstance(confidence, bool):
        raise ValueError("confidence must be finite and between 0.5 and 1")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be finite and between 0.5 and 1") from exc
    if not isfinite(confidence) or not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be finite and between 0.5 and 1")
    if not values:
        return {"status": "INSUFFICIENT_DATA", "n": 0, "mean_pct": None, "ci_low_pct": None, "ci_high_pct": None}
    rng = Random(seed)
    estimates = sorted(_mean(_block_sample(values, min(block_size, len(values)), rng)) for _ in range(reps))
    alpha = (1.0 - confidence) / 2.0
    low_i = max(0, min(reps - 1, int(alpha * reps)))
    high_i = max(0, min(reps - 1, int((1.0 - alpha) * reps) - 1))
    return {
        "status": "OK" if len(values) >= 20 else "LOW_SAMPLE",
        "n": len(values),
        "mean_pct": round(_mean(values), 6),
        "ci_low_pct": round(estimates[low_i], 6),
        "ci_high_pct": round(estimates[high_i], 6),
        "confidence": confidence,
        "bootstrap_reps": reps,
        "block_size": min(block_size, len(values)),
        "method": "circular_moving_block_percentile",
    }


def bootstrap_edge_test(
    candidate_returns: Iterable[float], baseline_returns: Iterable[float], *,
    reps: int = 4000, block_size: int = 3, seed: int = 20261024,
) -> dict:
    candidate = _values(candidate_returns, "candidate_returns")
    baseline = _values(baseline_returns, "baseline_returns")
    _validate_sampling(reps, block_size)
    if len(candidate) < 5 or len(baseline) < 5:
        return {
            "status": "INSUFFICIENT_DATA", "candidate_n": len(candidate),
            "baseline_n": len(baseline), "edge_mean_pct_points": None,
            "ci_low_pct_points": None, "ci_high_pct_points": None, "p_value_one_sided": None,
        }
    observed = _mean(candidate) - _mean(baseline)
    rng = Random(seed)
    differences = []
    null_candidate = [x - _mean(candidate) for x in candidate]
    null_baseline = [x - _mean(baseline) for x in baseline]
    at_least_observed = 0
    for _ in range(reps):
        c = _block_sample(candidate, min(block_size, len(candidate)), rng)
        b = _block_sample(baseline, min(block_size, len(baseline)), rng)
        differences.append(_mean(c) - _mean(b))
        cn = _block_sample(null_candidate, min(block_size, len(candidate)), rng)
        bn = _block_sample(null_baseline, min(block_size, len(baseline)), rng)
        if _mean(cn) - _mean(bn) >= observed:
            at_least_observed += 1
    differences.sort()
    low_i = max(0, min(reps - 1, int(0.025 * reps)))
    high_i = max(0, min(reps - 1, int(0.975 * reps) - 1))
    return {
        "status": "OK" if min(len(candidate), len(baseline)) >= 20 else "LOW_SAMPLE",
        "candidate_n": len(candidate),
        "baseline_n": len(baseline),
        "edge_mean_pct_points": round(observed, 6),
        "ci_low_pct_points": round(differences[low_i], 6),
        "ci_high_pct_points": round(differences[high_i], 6),
        "p_value_one_sided": round((at_least_observed + 1) / (reps + 1), 6),
        "method": "independent_circular_moving_block_bootstrap",
        "bootstrap_reps": reps,
        "block_size": block_size,
    }


def holm_adjust(p_values: Sequence[float | None]) -> list[float | None]:
    """Holm-Bonferroni adjusted p-values, preserving missing entries."""
    indexed = []
    output: list[float | None] = [None] * len(p_values)
    for i, value in enumerate(p_values):
        if value is None:
            continue
        if isinstance(value, bool):
            raise ValueError("p-values must be finite numbers in [0, 1]")
        p = float(value)
        if not isfinite(p) or not 0.0 <= p <= 1.0:
            raise ValueError("p-values must be finite and in [0, 1]")
        indexed.append((i, p))
    indexed.sort(key=lambda pair: pair[1])
    running = 0.0
    m = len(indexed)
    for rank, (index, p) in enumerate(indexed):
        adjusted = min(1.0, (m - rank) * p)
        running = max(running, adjusted)
        output[index] = round(running, 6)
    return output
