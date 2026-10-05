from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MemeCandidate:
    token: str
    liquidity_usd: float
    volume_24h_usd: float
    holders: int
    top_holder_pct: float
    buy_sell_ratio: float
    smart_money_score: float
    fomo_score: float
    risk_score: float
    quality_score: float
    status: str


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_meme_candidate(
    token: str,
    *,
    liquidity_usd: float,
    volume_24h_usd: float,
    holders: int,
    top_holder_pct: float,
    buy_sell_ratio: float,
    smart_money_score: float,
    fomo_score: float,
) -> MemeCandidate:
    liquidity = _clip01(liquidity_usd / 1_000_000.0)
    volume = _clip01(volume_24h_usd / 5_000_000.0)
    holder_growth_proxy = _clip01(holders / 10_000.0)
    concentration = _clip01(top_holder_pct / 50.0)
    flow = _clip01(buy_sell_ratio / 2.0)
    smart = _clip01(smart_money_score)
    fomo = _clip01(fomo_score)

    risk = _clip01(
        0.45 * concentration
        + 0.30 * (1.0 - liquidity)
        + 0.25 * (1.0 - holder_growth_proxy)
    )
    quality = _clip01(
        0.18 * liquidity
        + 0.12 * volume
        + 0.12 * holder_growth_proxy
        + 0.18 * flow
        + 0.25 * smart
        + 0.15 * fomo
        - 0.30 * risk
    )

    status = "WATCH"
    if quality >= 0.70 and risk < 0.45:
        status = "STRONG_WATCH"
    elif risk >= 0.70:
        status = "HIGH_RISK"

    return MemeCandidate(
        token=token,
        liquidity_usd=liquidity_usd,
        volume_24h_usd=volume_24h_usd,
        holders=int(holders),
        top_holder_pct=top_holder_pct,
        buy_sell_ratio=buy_sell_ratio,
        smart_money_score=round(smart, 6),
        fomo_score=round(fomo, 6),
        risk_score=round(risk, 6),
        quality_score=round(quality, 6),
        status=status,
    )


def rank_meme_candidates(candidates: Iterable[MemeCandidate]) -> list[MemeCandidate]:
    return sorted(
        candidates,
        key=lambda x: (x.status != "HIGH_RISK", x.quality_score, x.smart_money_score),
        reverse=True,
    )
