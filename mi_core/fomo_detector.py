from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .fomo_baseline import build_baseline


@dataclass(frozen=True)
class FomoEvent:
    symbol: str
    timestamp: int
    score: float
    abnormal_volume: bool
    volume_z: float
    percentile: float
    acceleration: float
    divergence: float
    trader_persistence: float = 0.0


def detect_fomo_event(
    symbol: str,
    timestamp: int,
    volume_history: Sequence[float],
    current_volume: float,
    price_history: Sequence[float] | None = None,
    current_price: float | None = None,
    trader_persistence: float = 0.0,
    z_threshold: float = 2.0,
) -> FomoEvent | None:
    baseline = build_baseline(
        volume_history,
        current_volume,
        price_history=price_history,
        current_price=current_price,
        z_threshold=z_threshold,
    )
    if not baseline.abnormal:
        return None

    persistence = max(0.0, min(1.0, float(trader_persistence)))
    # Persistence is a confidence enhancer, never the trigger.
    score = max(
        0.0,
        min(
            1.0,
            0.80 * baseline.score + 0.20 * persistence,
        ),
    )
    return FomoEvent(
        symbol=symbol,
        timestamp=int(timestamp),
        score=round(score, 6),
        abnormal_volume=True,
        volume_z=baseline.z,
        percentile=baseline.percentile,
        acceleration=baseline.acceleration,
        divergence=baseline.divergence,
        trader_persistence=round(persistence, 6),
    )
