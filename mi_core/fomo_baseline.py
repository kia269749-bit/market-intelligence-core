from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Sequence


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def z_score(history: Sequence[float], current: float) -> float:
    if not history:
        return 0.0
    sigma = pstdev(history)
    if sigma == 0:
        return 0.0
    return (current - mean(history)) / sigma


def percentile_rank(history: Sequence[float], current: float) -> float:
    if not history:
        return 0.5
    return sum(x <= current for x in history) / len(history)


def acceleration(history: Sequence[float]) -> float:
    if len(history) < 3:
        return 0.0
    return (history[-1] - history[-2]) - (history[-2] - history[-3])


def abnormality_score(history: Sequence[float], current: float, z_threshold: float = 2.0) -> float:
    z = z_score(history, current)
    if z_threshold <= 0:
        raise ValueError("z_threshold must be positive")
    return _clip01((z - z_threshold) / z_threshold)


def price_volume_divergence(price_history: Sequence[float], volume_history: Sequence[float]) -> float:
    if len(price_history) < 2 or len(volume_history) < 2:
        return 0.0
    n = min(len(price_history), len(volume_history))
    price_delta = price_history[-1] - price_history[-n]
    volume_delta = volume_history[-1] - volume_history[-n]
    if price_delta == 0 or volume_delta == 0:
        return 0.0
    if (price_delta > 0 and volume_delta < 0) or (price_delta < 0 and volume_delta > 0):
        return _clip01(abs(volume_delta) / max(abs(volume_history[-n]), 1.0))
    return 0.0


@dataclass(frozen=True)
class FomoBaseline:
    z: float
    percentile: float
    acceleration: float
    abnormal_volume: float
    divergence: float
    score: float
    abnormal: bool


def build_baseline(
    volume_history: Sequence[float],
    current_volume: float,
    price_history: Sequence[float] | None = None,
    current_price: float | None = None,
    z_threshold: float = 2.0,
) -> FomoBaseline:
    history = list(volume_history)
    z = z_score(history, current_volume)
    pct = percentile_rank(history, current_volume)
    acc = acceleration(history + [current_volume])
    abnormal = abnormality_score(history, current_volume, z_threshold)

    divergence = 0.0
    if price_history is not None and current_price is not None:
        divergence = price_volume_divergence(
            list(price_history) + [current_price],
            history + [current_volume],
        )

    z_component = _clip01((z - 1.0) / max(z_threshold, 1.0))
    pct_component = _clip01((pct - 0.80) / 0.20)
    acc_component = _clip01(acc / max(abs(mean(history)) if history else 1.0, 1.0))
    score = _clip01(
        0.55 * z_component
        + 0.20 * pct_component
        + 0.10 * acc_component
        + 0.15 * divergence
    )

    return FomoBaseline(
        z=round(z, 6),
        percentile=round(pct, 6),
        acceleration=round(acc, 6),
        abnormal_volume=round(abnormal, 6),
        divergence=round(divergence, 6),
        score=round(score, 6),
        abnormal=z >= z_threshold,
    )
