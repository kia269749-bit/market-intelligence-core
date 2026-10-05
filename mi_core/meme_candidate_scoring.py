from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


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
    historical_evidence_score: float = 0.0
    historical_evidence_status: str = "UNAVAILABLE"


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _historical_evidence(evidence: Mapping | None) -> tuple[float, str]:
    if not evidence:
        return 0.0, "UNAVAILABLE"
    oos = evidence.get("oos", {})
    anti = evidence.get("anti_overfitting", {})
    pf = oos.get("profit_factor")
    trades = int(oos.get("trades_count", 0))
    score = float(anti.get("score", 0.0))
    if isinstance(pf, (int, float)) and pf >= 1.0 and trades > 0:
        score = _clip01(0.6 * score + 0.4 * _clip01(float(pf) / 2.0))
    else:
        score *= 0.5
    status = "SUPPORTED" if score >= 0.60 else "WEAK" if score > 0 else "UNAVAILABLE"
    return round(score, 6), status


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
    historical_evidence: Mapping | None = None,
) -> MemeCandidate:
    liquidity = _clip01(liquidity_usd / 1_000_000.0)
    volume = _clip01(volume_24h_usd / 5_000_000.0)
    holder_growth_proxy = _clip01(holders / 10_000.0)
    concentration = _clip01(top_holder_pct / 50.0)
    flow = _clip01(buy_sell_ratio / 2.0)
    smart = _clip01(smart_money_score)
    fomo = _clip01(fomo_score)
    history_score, history_status = _historical_evidence(historical_evidence)

    risk = _clip01(0.45 * concentration + 0.30 * (1.0 - liquidity) + 0.25 * (1.0 - holder_growth_proxy))
    quality = _clip01(
        0.16 * liquidity + 0.10 * volume + 0.10 * holder_growth_proxy
        + 0.16 * flow + 0.22 * smart + 0.12 * fomo
        + 0.14 * history_score - 0.30 * risk
    )
    status = "WATCH"
    if quality >= 0.70 and risk < 0.45 and history_status != "WEAK":
        status = "STRONG_WATCH"
    elif risk >= 0.70:
        status = "HIGH_RISK"

    return MemeCandidate(
        token=token, liquidity_usd=liquidity_usd, volume_24h_usd=volume_24h_usd,
        holders=int(holders), top_holder_pct=top_holder_pct, buy_sell_ratio=buy_sell_ratio,
        smart_money_score=round(smart, 6), fomo_score=round(fomo, 6),
        risk_score=round(risk, 6), quality_score=round(quality, 6), status=status,
        historical_evidence_score=history_score, historical_evidence_status=history_status,
    )


def rank_meme_candidates(candidates: Iterable[MemeCandidate]) -> list[MemeCandidate]:
    status_priority = {"STRONG_WATCH": 2, "WATCH": 1, "HIGH_RISK": 0}
    return sorted(candidates, key=lambda x: (status_priority.get(x.status, -1), x.quality_score, x.smart_money_score), reverse=True)
