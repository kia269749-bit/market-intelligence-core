"""Research-only validation helpers for OOS and Monte Carlo robustness."""
from __future__ import annotations
from dataclasses import asdict
from typing import Sequence
from .monte_carlo import anti_overfitting_score, monte_carlo_bootstrap

def validate_oos_robustness(oos_report: dict, trade_returns: Sequence[float], *,
    train_return: float = 0.0, simulations: int = 2000, seed: int = 42,
    min_oos_positive_rate: float = 0.50, max_loss_probability: float = 0.50) -> dict:
    mc = monte_carlo_bootstrap(trade_returns, simulations=simulations, seed=seed)
    anti = anti_overfitting_score(
        train_return=train_return,
        oos_return=float(oos_report.get("oos_return_total", 0.0)),
        oos_positive_rate=float(oos_report.get("oos_positive_rate", 0.0)),
        oos_probability_of_loss=mc.probability_of_loss,
        min_oos_positive_rate=min_oos_positive_rate,
        max_loss_probability=max_loss_probability,
    )
    return {
        "oos": oos_report,
        "monte_carlo": asdict(mc),
        "anti_overfitting": anti,
        "robustness_pass": bool(
            anti["oos_positive"] and anti["oos_positive_rate_pass"]
            and anti["loss_probability_pass"] and mc.p05_return > -1.0
        ),
        "research_only": True,
        "live_orders": False,
    }
