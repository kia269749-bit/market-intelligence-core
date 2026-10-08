"""Research-only robustness, regime stress, and multiple-testing diagnostics."""
from __future__ import annotations
import math, statistics
from typing import Sequence

def _mean(xs):
    return statistics.fmean(xs) if xs else 0.0

def _std(xs):
    return statistics.stdev(xs) if len(xs) > 1 else 0.0

def classify_regime(prices: Sequence[float], *, trend_window: int = 20, vol_window: int = 20) -> str:
    """Simple causal regime label using data available through the current bar."""
    if len(prices) < max(trend_window, vol_window) + 1:
        return "UNKNOWN"
    p = [float(x) for x in prices]
    rets = [math.log(p[i] / p[i-1]) for i in range(1, len(p)) if p[i] > 0 and p[i-1] > 0]
    if len(rets) < vol_window:
        return "UNKNOWN"
    vol = _std(rets[-vol_window:])
    mean_px = _mean(p[-trend_window:])
    last = p[-1]
    if vol >= 0.04:
        return "HIGH_VOL"
    if last > mean_px * 1.01:
        return "BULL"
    if last < mean_px * 0.99:
        return "BEAR"
    return "RANGE"

def regime_stress(predictions, prices: Sequence[float], *, min_samples: int = 50) -> dict:
    """Evaluate OOS prediction net outcomes by causal market regime."""
    buckets = {}
    for row in predictions:
        try:
            idx = int(row.get("_index"))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(prices) or row.get("pred") not in (-1, 1):
            continue
        regime = classify_regime(prices[:idx+1])
        r = row.get("actual_return_pct")
        if r is None:
            continue
        favorable = float(r) if int(row["pred"]) == 1 else -float(r)
        buckets.setdefault(regime, []).append(favorable)
    out = {}
    for regime, vals in buckets.items():
        wins = sum(v > 0 for v in vals)
        out[regime] = {
            "samples": len(vals),
            "mean_favorable_return_pct": round(_mean(vals), 6),
            "positive_rate": round(wins / len(vals), 6),
            "min_sample_gate": len(vals) >= min_samples,
            "stress_pass": len(vals) >= min_samples and _mean(vals) > 0 and wins / len(vals) >= 0.50,
        }
    valid = [v for v in out.values() if v["min_sample_gate"]]
    return {
        "regimes": out,
        "covered_regimes": len(out),
        "sample_qualified_regimes": len(valid),
        "all_qualified_pass": bool(valid) and all(v["stress_pass"] for v in valid),
        "research_only": True,
        "live_orders": False,
    }

def _skewness(xs):
    if len(xs) < 3:
        return 0.0
    s = _std(xs)
    if s == 0:
        return 0.0
    m = _mean(xs)
    return _mean([((x-m)/s)**3 for x in xs])

def _kurtosis_excess(xs):
    if len(xs) < 4:
        return 0.0
    s = _std(xs)
    if s == 0:
        return 0.0
    m = _mean(xs)
    return _mean([((x-m)/s)**4 for x in xs]) - 3.0

def sharpe_ratio(returns: Sequence[float], annualization: float = 1.0) -> float:
    s = _std(returns)
    return (_mean(returns) / s) * math.sqrt(annualization) if s else 0.0

def probabilistic_sharpe_ratio(returns: Sequence[float], benchmark: float = 0.0) -> float:
    """Approximate PSR: probability true Sharpe exceeds benchmark."""
    n = len(returns)
    if n < 3:
        return 0.0
    sr = sharpe_ratio(returns)
    skew = _skewness(returns)
    kurt = _kurtosis_excess(returns)
    denom = math.sqrt(max(1e-12, (1 - skew*sr + ((kurt + 3) / 4.0) * sr*sr) / (n - 1)))
    z = (sr - benchmark) / denom
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def deflated_sharpe_ratio(returns: Sequence[float], *, trials: int = 1, benchmark: float = 0.0) -> dict:
    """Research diagnostic correcting Sharpe optimism from multiple tried variants."""
    n = len(returns)
    trials = max(1, int(trials))
    raw = sharpe_ratio(returns)
    psr = probabilistic_sharpe_ratio(returns, benchmark)
    skew = _skewness(returns)
    kurt = _kurtosis_excess(returns)
    if trials == 1:
        expected_max = 0.0
    else:
        p = max(1e-6, min(1 - 1e-6, 1.0 - 1.0 / trials))
        z = math.sqrt(2.0) * math.erfinv(2.0*p - 1.0) if hasattr(math, "erfinv") else _normal_ppf(p)
        expected_max = z * math.sqrt(max(1e-12, (1 - skew*0.0 + ((kurt + 3) / 4.0)*0.0) / max(1, n-1)))
    dsr = probabilistic_sharpe_ratio(returns, benchmark=max(benchmark, expected_max))
    return {
        "samples": n,
        "trials": trials,
        "raw_sharpe": round(raw, 6),
        "expected_max_sharpe_proxy": round(expected_max, 6),
        "probability_sharpe_gt_benchmark": round(psr, 6),
        "deflated_sharpe_probability": round(dsr, 6),
        "pass_95pct": bool(n >= 30 and dsr >= 0.95),
        "research_only": True,
        "live_orders": False,
    }

def _normal_ppf(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")
    return statistics.NormalDist().inv_cdf(p)

def overfit_diagnostic(train_return: float, oos_return: float, *, variants_tested: int = 1) -> dict:
    train=float(train_return); oos=float(oos_return)
    decay = 0.0 if train <= 0 else max(0.0, 1.0 - oos/train)
    return {
        "train_return": round(train, 8),
        "oos_return": round(oos, 8),
        "train_oos_decay": round(decay, 6),
        "variants_tested": max(1, int(variants_tested)),
        "oos_positive": oos > 0,
        "severe_decay": decay > 0.50 if train > 0 else False,
        "research_only": True,
        "live_orders": False,
    }
