from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class TradeDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class DirectionEvidence:
    source: str
    direction: TradeDirection
    strength: float
    detail: str = ""

@dataclass(frozen=True)
class DirectionResult:
    direction: TradeDirection
    confidence: float
    evidence: tuple[DirectionEvidence, ...]
    conflicts: tuple[str, ...]
    reliable: bool
    def to_dict(self) -> dict:
        return {"direction": self.direction.value, "confidence": self.confidence,
                "evidence": [{"source": e.source, "direction": e.direction.value, "strength": e.strength, "detail": e.detail} for e in self.evidence],
                "conflicts": list(self.conflicts), "reliable": self.reliable}

def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def _delta_direction(target_delta: float, quote_delta: float | None):
    if target_delta > 0:
        if quote_delta is not None and quote_delta < 0:
            return TradeDirection.BUY, 1.0, "target token increased while quote balance decreased"
        return TradeDirection.BUY, 0.70, "target token balance increased"
    if target_delta < 0:
        if quote_delta is not None and quote_delta > 0:
            return TradeDirection.SELL, 1.0, "target token decreased while quote balance increased"
        return TradeDirection.SELL, 0.70, "target token balance decreased"
    return TradeDirection.UNKNOWN, 0.0, "target token balance did not change"

def _as_direction(value) -> TradeDirection | None:
    if value is None:
        return None
    if isinstance(value, TradeDirection):
        return value
    try:
        return TradeDirection(str(value).upper())
    except ValueError:
        return None

def infer_direction(*, target_token_delta: float, quote_token_delta: float | None = None,
                    dex_direction=None, pool_direction=None, clmm_is_base_input: bool | None = None,
                    min_reliable_confidence: float = 0.60) -> DirectionResult:
    evidence = []
    delta_dir, delta_strength, detail = _delta_direction(target_token_delta, quote_token_delta)
    if delta_dir is not TradeDirection.UNKNOWN:
        evidence.append(DirectionEvidence("token_delta", delta_dir, delta_strength, detail))
    for source, value in (("dex", dex_direction), ("pool_vault", pool_direction)):
        direction = _as_direction(value)
        if direction in (TradeDirection.BUY, TradeDirection.SELL):
            evidence.append(DirectionEvidence(source, direction, 0.95, "DEX/pool direction evidence"))
    if clmm_is_base_input is not None:
        direction = TradeDirection.BUY if clmm_is_base_input else TradeDirection.SELL
        evidence.append(DirectionEvidence("clmm_is_base_input", direction, 0.80, "CLMM input-side direction"))
    if not evidence:
        return DirectionResult(TradeDirection.UNKNOWN, 0.0, (), (), False)
    buy = sum(e.strength for e in evidence if e.direction is TradeDirection.BUY)
    sell = sum(e.strength for e in evidence if e.direction is TradeDirection.SELL)
    winner = TradeDirection.BUY if buy > sell else TradeDirection.SELL
    loser = TradeDirection.SELL if winner is TradeDirection.BUY else TradeDirection.BUY
    total = buy + sell
    agreement = (buy if winner is TradeDirection.BUY else sell) / total if total else 0.0
    winner_count = sum(1 for e in evidence if e.direction is winner)
    confidence = _clip01((0.45 + 0.20 * min(2, max(0, winner_count - 1))) * agreement)
    conflicts = tuple(f"{e.source} disagrees with majority direction" for e in evidence if e.direction is loser)
    reliable = confidence >= min_reliable_confidence and agreement >= 0.65
    if not reliable:
        return DirectionResult(TradeDirection.UNKNOWN, round(confidence, 6), tuple(evidence), conflicts, False)
    return DirectionResult(winner, round(confidence, 6), tuple(evidence), conflicts, True)

def direction_from_fill(*, target_token_delta: float, quote_token_delta: float | None = None, **kwargs) -> DirectionResult:
    return infer_direction(target_token_delta=target_token_delta, quote_token_delta=quote_token_delta, **kwargs)
