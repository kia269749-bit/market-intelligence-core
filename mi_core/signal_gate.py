"""Research-only adaptive thresholds and signal quality gating."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SignalQuality:
    score: float
    confidence: float
    edge: float
    data_quality: float
    regime_fit: float
    decay: float

@dataclass(frozen=True)
class SignalGateConfig:
    min_score: float = 0.60
    min_confidence: float = 0.55
    min_edge: float = 0.0
    min_data_quality: float = 0.80
    min_regime_fit: float = 0.50
    min_decay: float = 0.50

def adaptive_threshold(scores, base: float = 0.60, window: int = 100) -> float:
    values = list(scores)[-window:]
    if not values:
        return base
    if window < 1:
        raise ValueError("window must be positive")
    mean = sum(values) / len(values)
    vol = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
    return max(0.45, min(0.85, base + 0.25 * vol))

def signal_quality_gate(q: SignalQuality, cfg: SignalGateConfig | None = None) -> dict:
    cfg = cfg or SignalGateConfig()
    values = (q.score, q.confidence, q.data_quality, q.regime_fit, q.decay)
    if any(not 0 <= x <= 1 for x in values):
        raise ValueError("bounded signal quality values must be between 0 and 1")
    checks = {
        "score": q.score >= cfg.min_score,
        "confidence": q.confidence >= cfg.min_confidence,
        "edge": q.edge >= cfg.min_edge,
        "data_quality": q.data_quality >= cfg.min_data_quality,
        "regime_fit": q.regime_fit >= cfg.min_regime_fit,
        "decay": q.decay >= cfg.min_decay,
    }
    return {"eligible": all(checks.values()), "checks": checks,
            "reasons": tuple(k for k, passed in checks.items() if not passed),
            "diagnostic_only": True}

def risk_kill_switch(equity: float, peak: float, drawdown_limit: float = 0.20) -> bool:
    if peak <= 0 or not 0 < drawdown_limit <= 1:
        raise ValueError("peak must be positive and drawdown_limit must be in (0, 1]")
    return (peak - equity) / peak >= drawdown_limit
