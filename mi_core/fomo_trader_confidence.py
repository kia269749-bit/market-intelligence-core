from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FomoTraderConfidence:
    trader_id: str
    historical_score: float
    rank_score: float
    pnl_positive_rate: float
    sample_confidence: float
    meme_edge: float
    confidence: float
    eligible: bool


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def trader_confidence(
    metrics: Mapping[str, float],
    *,
    min_snapshots: int = 3,
    min_confidence: float = 0.60,
) -> FomoTraderConfidence:
    snapshots = int(metrics.get("snapshots", 0))
    historical = _clip01(metrics.get("historical_score", 0.0))
    rank_score = _clip01(metrics.get("rank_score", 0.0))
    pnl_positive = _clip01(metrics.get("pnl_positive_rate", 0.0))
    sample = _clip01(metrics.get("sample_confidence", 0.0))
    meme_edge = _clip01(metrics.get("meme_edge", 0.0))

    confidence = _clip01(
        0.35 * historical
        + 0.20 * rank_score
        + 0.20 * pnl_positive
        + 0.15 * sample
        + 0.10 * meme_edge
    )
    eligible = snapshots >= min_snapshots and confidence >= min_confidence

    return FomoTraderConfidence(
        trader_id=str(metrics.get("trader_id", "")),
        historical_score=round(historical, 6),
        rank_score=round(rank_score, 6),
        pnl_positive_rate=round(pnl_positive, 6),
        sample_confidence=round(sample, 6),
        meme_edge=round(meme_edge, 6),
        confidence=round(confidence, 6),
        eligible=eligible,
    )


def attach_trader_confidence(
    ranked_traders: list[Mapping[str, float]],
    *,
    min_snapshots: int = 3,
    min_confidence: float = 0.60,
) -> list[dict]:
    output = []
    for metrics in ranked_traders:
        row = dict(metrics)
        result = trader_confidence(
            row,
            min_snapshots=min_snapshots,
            min_confidence=min_confidence,
        )
        row["fomo_trader_confidence"] = result.confidence
        row["fomo_trader_eligible"] = result.eligible
        output.append(row)
    output.sort(
        key=lambda x: (
            x["fomo_trader_confidence"],
            x.get("historical_score", 0.0),
            x.get("pnl_usd_latest", 0.0),
        ),
        reverse=True,
    )
    return output
