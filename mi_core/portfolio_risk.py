"""Research-only portfolio risk intelligence and regime-aware sizing."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PositionCandidate:
    symbol: str
    confidence: float
    edge: float
    regime_fit: float
    stop_distance: float
    regime: str

@dataclass(frozen=True)
class PortfolioRiskConfig:
    risk_fraction: float = 0.01
    max_position_risk: float = 0.02
    max_portfolio_risk: float = 0.06
    max_correlation_penalty: float = 0.25

def regime_multiplier(regime: str) -> float:
    return {"BULL": 1.0, "BEAR": 1.0, "RANGE": 0.75, "HIGH_VOL": 0.50}.get(regime, 0.50)

def position_risk_fraction(candidate: PositionCandidate, cfg: PortfolioRiskConfig | None = None) -> float:
    cfg = cfg or PortfolioRiskConfig()
    if not 0 <= candidate.confidence <= 1 or not 0 <= candidate.regime_fit <= 1:
        raise ValueError("confidence and regime_fit must be between 0 and 1")
    if candidate.stop_distance <= 0:
        raise ValueError("stop_distance must be positive")
    raw = cfg.risk_fraction * max(0.0, candidate.confidence) * max(0.0, candidate.regime_fit)
    raw *= max(0.0, 1.0 + candidate.edge)
    return min(cfg.max_position_risk, raw * regime_multiplier(candidate.regime))

def portfolio_risk_gate(position_risks, correlation_penalty: float = 0.0,
                         cfg: PortfolioRiskConfig | None = None) -> dict:
    cfg = cfg or PortfolioRiskConfig()
    risks = [float(x) for x in position_risks]
    if any(x < 0 for x in risks) or correlation_penalty < 0:
        raise ValueError("risks and correlation_penalty must be nonnegative")
    total = sum(risks)
    adjusted = total + correlation_penalty
    checks = {
        "total_risk": total <= cfg.max_portfolio_risk,
        "correlation_penalty": correlation_penalty <= cfg.max_correlation_penalty,
    }
    return {"eligible": all(checks.values()), "total_risk": total,
            "adjusted_risk": adjusted, "checks": checks,
            "diagnostic_only": True}
