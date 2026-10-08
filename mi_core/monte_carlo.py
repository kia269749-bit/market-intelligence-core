"""Research-only Monte Carlo and anti-overfitting validation utilities."""
from __future__ import annotations
from dataclasses import dataclass
import math
import random
from statistics import mean
from typing import Sequence

@dataclass(frozen=True)
class MonteCarloResult:
    simulations: int
    seed: int
    mean_return: float
    p05_return: float
    median_return: float
    p95_return: float
    probability_of_loss: float
    probability_of_positive: float
    mean_max_drawdown: float
    p95_max_drawdown: float

def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values must not be empty")
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

def _path_metrics(returns: Sequence[float]) -> tuple[float, float]:
    # Use simple additive trade returns, not compounded hourly-bar returns.
    # Compounding thousands of forecast-bar returns can create meaningless
    # astronomical diagnostics that are not comparable with the OOS economics.
    equity = peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity += r
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return equity - 1.0, max_dd

def monte_carlo_bootstrap(trade_returns: Sequence[float], *, simulations: int = 2000, seed: int = 42) -> MonteCarloResult:
    if not trade_returns:
        raise ValueError("trade_returns must not be empty")
    if simulations < 100:
        raise ValueError("simulations must be at least 100")
    if any(r <= -1.0 for r in trade_returns):
        raise ValueError("trade returns must be greater than -100%")
    rng = random.Random(seed)
    source = [float(r) for r in trade_returns]
    returns, drawdowns = [], []
    for _ in range(simulations):
        path = [source[rng.randrange(len(source))] for _ in source]
        result, dd = _path_metrics(path)
        returns.append(result)
        drawdowns.append(dd)
    return MonteCarloResult(
        simulations=simulations, seed=seed, mean_return=mean(returns),
        p05_return=_percentile(returns, .05), median_return=_percentile(returns, .50),
        p95_return=_percentile(returns, .95),
        probability_of_loss=sum(r < 0 for r in returns) / simulations,
        probability_of_positive=sum(r > 0 for r in returns) / simulations,
        mean_max_drawdown=mean(drawdowns), p95_max_drawdown=_percentile(drawdowns, .95),
    )

def anti_overfitting_score(*, train_return: float, oos_return: float, oos_positive_rate: float,
                           oos_probability_of_loss: float, min_oos_positive_rate: float = .50,
                           max_loss_probability: float = .50) -> dict:
    if not 0 <= oos_positive_rate <= 1:
        raise ValueError("oos_positive_rate must be between 0 and 1")
    if not 0 <= oos_probability_of_loss <= 1:
        raise ValueError("oos_probability_of_loss must be between 0 and 1")
    if min_oos_positive_rate <= 0 or min_oos_positive_rate > 1:
        raise ValueError("min_oos_positive_rate must be in (0, 1]")
    if not 0 <= max_loss_probability <= 1:
        raise ValueError("max_loss_probability must be between 0 and 1")
    train, oos = float(train_return), float(oos_return)
    decay = 0.0 if train <= 0 else max(0.0, min(1.0, 1.0 - oos / train))
    score = max(0.0, min(1.0, .35*(oos > 0) + .30*min(1.0, oos_positive_rate/min_oos_positive_rate)
                  + .20*(1.0-min(1.0, oos_probability_of_loss/max(max_loss_probability,1e-12)))
                  + .15*(1.0-decay)))
    return {"score": round(score,6), "oos_positive": oos > 0,
            "oos_positive_rate_pass": oos_positive_rate >= min_oos_positive_rate,
            "loss_probability_pass": oos_probability_of_loss <= max_loss_probability,
            "train_oos_decay": round(decay,6), "diagnostic_only": True}
