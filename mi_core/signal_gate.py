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
    if not values: return base
    if window < 1: raise ValueError("window must be positive")
    mean = sum(values) / len(values)
    vol = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
    return max(0.45, min(0.85, base + 0.25 * vol))

def signal_quality_gate(q: SignalQuality, cfg: SignalGateConfig | None = None) -> dict:
    cfg = cfg or SignalGateConfig()
    values = (q.score, q.confidence, q.data_quality, q.regime_fit, q.decay)
    if any(not 0 <= x <= 1 for x in values): raise ValueError("bounded signal quality values must be between 0 and 1")
    checks = {"score": q.score >= cfg.min_score, "confidence": q.confidence >= cfg.min_confidence,
              "edge": q.edge >= cfg.min_edge, "data_quality": q.data_quality >= cfg.min_data_quality,
              "regime_fit": q.regime_fit >= cfg.min_regime_fit, "decay": q.decay >= cfg.min_decay}
    return {"eligible": all(checks.values()), "checks": checks,
            "reasons": tuple(k for k, passed in checks.items() if not passed), "diagnostic_only": True}

def research_signal_summary(*, side: str, signal_score: float, confidence: float,
    gate_eligible: bool, effective_confluence: float, agreement: float,
    crowding_score: float = 0.0, cascade_risk: bool = False,
    oi_funding_divergence: bool = False, regime_fit: float = 0.60,
    fomo_supported: bool = False, meme_supported: bool = False) -> dict:
    direction = side if side in {"LONG", "SHORT"} else "FLAT"
    directional_confluence = effective_confluence if direction == "LONG" else -effective_confluence if direction == "SHORT" else 0.0
    crowding_score = max(0.0, min(1.0, float(crowding_score)))
    regime_fit = max(0.0, min(1.0, float(regime_fit)))
    penalty = 0.15 * crowding_score + (0.15 if cascade_risk else 0.0) + (0.10 if oi_funding_divergence else 0.0)
    support_bonus = (0.04 if fomo_supported else 0.0) + (0.04 if meme_supported else 0.0)
    raw_conviction = (0.35 * signal_score + 0.25 * confidence + 0.25 * max(0.0, directional_confluence)
                      + 0.15 * agreement)
    conviction = max(0.0, min(1.0, raw_conviction - penalty + support_bonus))
    warnings = []
    if crowding_score >= 0.70: warnings.append("EXTREME_CROWDING")
    elif crowding_score >= 0.45: warnings.append("ELEVATED_CROWDING")
    if cascade_risk: warnings.append("LIQUIDATION_CASCADE_RISK")
    if oi_funding_divergence: warnings.append("OI_FUNDING_DIVERGENCE")
    if regime_fit < 0.50: warnings.append("POOR_MACRO_REGIME_FIT")
    if direction == "FLAT": status = "NO_SIGNAL"
    elif not gate_eligible: status = "FILTERED"
    elif conviction >= 0.75 and agreement >= 0.80 and directional_confluence >= 0.20 and not cascade_risk: status = "STRONG"
    elif conviction >= 0.60 and agreement >= 0.60: status = "WATCH"
    else: status = "WEAK"
    return {"direction": direction, "status": status, "conviction": round(conviction, 6),
            "raw_conviction": round(max(0.0, min(1.0, raw_conviction)), 6),
            "risk_penalty": round(penalty, 6), "support_bonus": round(support_bonus, 6),
            "regime_fit": round(regime_fit, 6), "warnings": tuple(warnings),
            "gate_eligible": bool(gate_eligible), "diagnostic_only": True, "manual_review": True}

def risk_kill_switch(equity: float, peak: float, drawdown_limit: float = 0.20) -> bool:
    if peak <= 0 or not 0 < drawdown_limit <= 1: raise ValueError("peak must be positive and drawdown_limit must be in (0, 1]")
    return (peak - equity) / peak >= drawdown_limit
