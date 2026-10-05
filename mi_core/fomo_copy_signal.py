from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from .fomo_smart_money import TraderAction, TrackedPosition
from .fomo_trader_confidence import FomoTraderConfidence
from .meme_candidate_scoring import MemeCandidate

@dataclass(frozen=True)
class FomoCopySignal:
    trader_id: str
    token: str
    action: str
    status: str
    score: float
    trader_confidence: float
    meme_quality: float
    meme_risk: float
    position_return_pct: float | None
    reasons: tuple[str, ...]

def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def build_fomo_copy_signal(action: TraderAction, trader: FomoTraderConfidence, candidate: MemeCandidate, *, position: TrackedPosition | None = None, min_trader_confidence: float = 0.60, min_meme_quality: float = 0.55, max_meme_risk: float = 0.70) -> FomoCopySignal:
    reasons: list[str] = []
    if not trader.eligible or trader.confidence < min_trader_confidence:
        return FomoCopySignal(action.trader_id, action.token, action.action, "IGNORE_UNQUALIFIED_TRADER", 0.0, trader.confidence, candidate.quality_score, candidate.risk_score, None if position is None else position.unrealized_return_pct, ("historical trader confidence below eligibility gate",))
    if candidate.risk_score >= max_meme_risk:
        return FomoCopySignal(action.trader_id, action.token, action.action, "BLOCK_HIGH_RISK", 0.0, trader.confidence, candidate.quality_score, candidate.risk_score, None if position is None else position.unrealized_return_pct, ("meme risk exceeds safety gate",))
    quality_component = _clip01(candidate.quality_score)
    trader_component = _clip01(trader.confidence)
    flow_component = _clip01(action.amount_usd / 10_000.0)
    score = _clip01(0.55 * trader_component + 0.30 * quality_component + 0.15 * flow_component)
    if action.action == "BUY":
        if candidate.quality_score < min_meme_quality:
            status = "WATCH_ONLY_LOW_QUALITY"
            reasons.append("candidate quality below follow threshold")
        else:
            status = "FOLLOW_CANDIDATE"
            reasons.append("eligible trader buy on acceptable meme candidate")
        if candidate.smart_money_score >= 0.70:
            reasons.append("strong smart-money context")
        if candidate.fomo_score >= 0.70:
            reasons.append("elevated FOMO context")
    elif action.action == "SELL":
        status = "EXIT_WATCH"
        reasons.append("eligible trader sell detected")
        if position is not None:
            reasons.append("tracked position is currently profitable" if position.unrealized_return_pct > 0 else "tracked position is not currently profitable")
    else:
        status = "IGNORE_UNKNOWN_ACTION"
        reasons.append("unsupported trader action")
    return FomoCopySignal(action.trader_id, action.token, action.action, status, round(score, 6), round(trader.confidence, 6), round(candidate.quality_score, 6), round(candidate.risk_score, 6), None if position is None else round(position.unrealized_return_pct, 6), tuple(reasons))

def rank_fomo_copy_signals(signals: Sequence[FomoCopySignal]) -> list[FomoCopySignal]:
    priority = {"FOLLOW_CANDIDATE": 4, "EXIT_WATCH": 3, "WATCH_ONLY_LOW_QUALITY": 2, "BLOCK_HIGH_RISK": 1, "IGNORE_UNQUALIFIED_TRADER": 0, "IGNORE_UNKNOWN_ACTION": 0}
    return sorted(signals, key=lambda x: (priority.get(x.status, 0), x.score, x.trader_confidence), reverse=True)
