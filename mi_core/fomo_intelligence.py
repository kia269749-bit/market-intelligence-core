from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .fomo_detector import FomoEvent, detect_fomo_event
from .fomo_trader_confidence import trader_confidence


@dataclass(frozen=True)
class FomoIntelligence:
    event: FomoEvent | None
    trader_confidence: float
    actionable_research_flag: bool


def analyze_fomo(
    *,
    symbol: str,
    timestamp: int,
    volume_history: Sequence[float],
    current_volume: float,
    trader_metrics: Mapping[str, float] | None = None,
    price_history: Sequence[float] | None = None,
    current_price: float | None = None,
    z_threshold: float = 2.0,
    min_confidence: float = 0.60,
) -> FomoIntelligence:
    confidence = 0.0
    eligible = False
    if trader_metrics is not None:
        result = trader_confidence(trader_metrics, min_confidence=min_confidence)
        confidence = result.confidence
        eligible = result.eligible

    event = detect_fomo_event(
        symbol=symbol,
        timestamp=timestamp,
        volume_history=volume_history,
        current_volume=current_volume,
        price_history=price_history,
        current_price=current_price,
        trader_persistence=confidence,
        z_threshold=z_threshold,
    )

    # Research flag requires BOTH independent conditions:
    # abnormal market volume and sufficiently reliable historical trader context.
    return FomoIntelligence(
        event=event,
        trader_confidence=round(confidence, 6),
        actionable_research_flag=bool(event and eligible),
    )
