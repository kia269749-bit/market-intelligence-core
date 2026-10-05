from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence
from .fomo_direction import TradeDirection

@dataclass(frozen=True)
class TraderFill:
    trader_id: str
    token: str
    timestamp: int
    direction: TradeDirection | str
    amount_usd: float
    confidence: float = 1.0
    tx_id: str | None = None
    def normalized_direction(self) -> TradeDirection:
        if isinstance(self.direction, TradeDirection):
            return self.direction
        try:
            return TradeDirection(str(self.direction).upper())
        except ValueError:
            return TradeDirection.UNKNOWN

@dataclass(frozen=True)
class LeaderFollowerEvent:
    leader_id: str
    token: str
    direction: TradeDirection
    leader_timestamp: int
    leader_amount_usd: float
    leader_score: float
    follower_ids: tuple[str, ...]
    follower_count: int
    follower_volume_usd: float
    median_lag_seconds: float
    confidence: float
    status: str
    def to_dict(self) -> dict:
        return {"leader_id": self.leader_id, "token": self.token, "direction": self.direction.value,
                "leader_timestamp": self.leader_timestamp, "leader_amount_usd": self.leader_amount_usd,
                "leader_score": self.leader_score, "follower_ids": list(self.follower_ids),
                "follower_count": self.follower_count, "follower_volume_usd": self.follower_volume_usd,
                "median_lag_seconds": self.median_lag_seconds, "confidence": self.confidence, "status": self.status}

def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def detect_leader_follower_events(fills: Sequence[TraderFill], leader_scores: Mapping[str, float],
                                  *, window_seconds: int = 300, min_leader_score: float = 0.60,
                                  min_fill_confidence: float = 0.60, min_followers: int = 2) -> list[LeaderFollowerEvent]:
    ordered = sorted(fills, key=lambda f: (int(f.timestamp), f.trader_id))
    events = []
    for leader in ordered:
        direction = leader.normalized_direction()
        score = _clip01(leader_scores.get(leader.trader_id, 0.0))
        if direction is TradeDirection.UNKNOWN or score < min_leader_score or leader.confidence < min_fill_confidence:
            continue
        unique = {}
        for candidate in ordered:
            if candidate.trader_id == leader.trader_id or candidate.token != leader.token:
                continue
            if candidate.normalized_direction() is not direction or candidate.confidence < min_fill_confidence:
                continue
            lag = int(candidate.timestamp) - int(leader.timestamp)
            if 0 < lag <= window_seconds:
                unique.setdefault(candidate.trader_id, candidate)
        if len(unique) < min_followers:
            continue
        lags = sorted(int(f.timestamp) - int(leader.timestamp) for f in unique.values())
        mid = len(lags) // 2
        median_lag = float(lags[mid]) if len(lags) % 2 else (lags[mid-1] + lags[mid]) / 2.0
        follower_volume = sum(max(0.0, float(f.amount_usd)) for f in unique.values())
        breadth = _clip01(len(unique) / 5.0)
        confidence = _clip01(0.45 * score + 0.25 * leader.confidence + 0.20 * breadth +
                             0.10 * _clip01(1.0 - median_lag / max(1.0, window_seconds)))
        events.append(LeaderFollowerEvent(leader.trader_id, leader.token, direction, int(leader.timestamp),
            float(leader.amount_usd), round(score, 6), tuple(unique.keys()), len(unique),
            round(follower_volume, 6), median_lag, round(confidence, 6), "LEADER_FOLLOWER_CONFIRMED"))
    return sorted(events, key=lambda e: (e.token, e.leader_timestamp, -e.confidence))

def rank_leader_follower_events(events: Sequence[LeaderFollowerEvent]) -> list[LeaderFollowerEvent]:
    return sorted(events, key=lambda e: (e.confidence, e.follower_count, e.follower_volume_usd, e.leader_score), reverse=True)
