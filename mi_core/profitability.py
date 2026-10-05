"""Research-only profitability and risk gating utilities."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ProfitabilityGateConfig:
    min_oos_return: float = 0.0
    max_oos_drawdown: float = 0.20
    min_oos_positive_rate: float = 0.50
    max_loss_probability: float = 0.50
    min_monte_carlo_p05_return: float = -0.10
    min_trades: int = 30

    def __post_init__(self) -> None:
        if not 0 <= self.max_oos_drawdown <= 1:
            raise ValueError("max_oos_drawdown must be between 0 and 1")
        if not 0 <= self.min_oos_positive_rate <= 1:
            raise ValueError("min_oos_positive_rate must be between 0 and 1")
        if not 0 <= self.max_loss_probability <= 1:
            raise ValueError("max_loss_probability must be between 0 and 1")
        if self.min_trades < 1:
            raise ValueError("min_trades must be at least 1")

@dataclass(frozen=True)
class ProfitabilityDecision:
    eligible: bool
    reasons: tuple[str, ...]
    checks: dict[str, bool]

def evaluate_profitability(*, oos_return: float, oos_drawdown: float,
    oos_positive_rate: float, monte_carlo_probability_of_loss: float,
    monte_carlo_p05_return: float, trade_count: int,
    config: ProfitabilityGateConfig | None = None) -> ProfitabilityDecision:
    cfg = config or ProfitabilityGateConfig()
    if not 0 <= oos_positive_rate <= 1:
        raise ValueError("oos_positive_rate must be between 0 and 1")
    if not 0 <= monte_carlo_probability_of_loss <= 1:
        raise ValueError("monte_carlo_probability_of_loss must be between 0 and 1")
    if oos_drawdown < 0:
        raise ValueError("oos_drawdown must be nonnegative")
    if trade_count < 0:
        raise ValueError("trade_count must be nonnegative")
    checks = {
        "oos_return": float(oos_return) >= cfg.min_oos_return,
        "oos_drawdown": float(oos_drawdown) <= cfg.max_oos_drawdown,
        "oos_positive_rate": float(oos_positive_rate) >= cfg.min_oos_positive_rate,
        "monte_carlo_loss_probability": float(monte_carlo_probability_of_loss) <= cfg.max_loss_probability,
        "monte_carlo_p05_return": float(monte_carlo_p05_return) >= cfg.min_monte_carlo_p05_return,
        "minimum_trades": int(trade_count) >= cfg.min_trades,
    }
    reasons = tuple(name for name, passed in checks.items() if not passed)
    return ProfitabilityDecision(not reasons, reasons, checks)
