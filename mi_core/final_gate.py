"""Research-only final validation gate for profitability and risk."""
from __future__ import annotations

from .signal_gate import risk_kill_switch


def profitability_gate(
    metrics: dict,
    *,
    min_trades: int = 30,
    min_profit_factor: float = 1.10,
    min_expectancy: float = 0.0,
) -> dict:
    trades = int(metrics.get("trades_count", metrics.get("trades", 0)))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    expectancy = float(metrics.get("expectancy", 0.0))
    checks = {
        "minimum_trades": trades >= min_trades,
        "profit_factor": profit_factor >= min_profit_factor,
        "expectancy": expectancy > min_expectancy,
    }
    return {
        "eligible": all(checks.values()),
        "checks": checks,
        "reasons": tuple(k for k, ok in checks.items() if not ok),
        "diagnostic_only": True,
    }


def risk_gate(
    metrics: dict,
    *,
    max_drawdown: float = 0.20,
    max_loss_probability: float = 0.50,
) -> dict:
    observed_dd = float(metrics.get("max_drawdown", 0.0))
    loss_probability = float(metrics.get("probability_of_loss", 0.0))
    checks = {
        "max_drawdown": observed_dd <= max_drawdown,
        "loss_probability": loss_probability <= max_loss_probability,
    }
    return {
        "eligible": all(checks.values()),
        "checks": checks,
        "reasons": tuple(k for k, ok in checks.items() if not ok),
        "diagnostic_only": True,
    }


def final_validation_gate(
    profitability: dict,
    risk: dict,
    robustness: dict,
    *,
    equity: float | None = None,
    peak: float | None = None,
    drawdown_limit: float = 0.20,
) -> dict:
    kill_switch = False
    if equity is not None and peak is not None:
        kill_switch = risk_kill_switch(equity, peak, drawdown_limit)

    passed = (
        profitability.get("eligible", False)
        and risk.get("eligible", False)
        and robustness.get("robustness_pass", False)
        and not kill_switch
    )
    return {
        "approved_for_research": passed,
        "profitability": profitability,
        "risk": risk,
        "robustness": robustness,
        "kill_switch": {"triggered": kill_switch, "diagnostic_only": True},
        "research_only": True,
        "live_orders": False,
    }
