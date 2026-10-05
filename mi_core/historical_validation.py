"""Research-only historical evidence for the current signal model."""
from __future__ import annotations

from typing import Sequence

from .backtest import run as run_backtest
from .intelligence import score_bar
from .monte_carlo import anti_overfitting_score, monte_carlo_bootstrap
from .walk_forward import walk_forward


def _signals(bars: Sequence, entry_threshold: float):
    signals = []
    for i, bar in enumerate(bars):
        recent = list(bars[max(0, i - 20):i])
        signals.append(score_bar(bar, recent, entry_threshold=entry_threshold))
    return signals


def _summary(result: dict) -> dict:
    return {
        "return": round(float(result["return"]), 6),
        "max_drawdown": round(float(result["max_drawdown"]), 6),
        "trades_count": int(result["trades_count"]),
        "win_rate": round(float(result["win_rate"]), 6),
        "profit_factor": round(float(result["profit_factor"]), 6) if result["profit_factor"] != float("inf") else "inf",
        "expectancy": round(float(result["expectancy"]), 8),
        "cost_total": round(float(result["cost_total"]), 8),
    }


def evaluate_historical_evidence(
    bars: Sequence,
    *,
    entry_threshold: float = 0.60,
    initial: float = 10000.0,
    fee_bps: float = 5.0,
    slippage_bps: float = 3.0,
    latency_bars: int = 1,
    hold_bars: int = 1,
    risk_fraction: float = 0.10,
    train_ratio: float = 0.70,
    simulations: int = 1000,
    seed: int = 42,
) -> dict:
    """Evaluate the deterministic signal model chronologically with OOS and Monte Carlo."""
    if len(bars) < 20:
        raise ValueError("at least 20 bars are required for historical evidence")
    if not 0.50 <= train_ratio < 1.0:
        raise ValueError("train_ratio must be in [0.50, 1.0)")

    signals = _signals(bars, entry_threshold)
    full = run_backtest(
        bars, signals, initial=initial, fee_bps=fee_bps, slippage_bps=slippage_bps,
        latency_bars=latency_bars, hold_bars=hold_bars, risk_fraction=risk_fraction,
    )
    split = max(10, min(len(bars) - 1, int(len(bars) * train_ratio)))
    train_bars, test_bars = bars[:split], bars[split:]
    train_signals = _signals(train_bars, entry_threshold)
    test_signals = _signals(test_bars, entry_threshold)
    train = run_backtest(
        train_bars, train_signals, initial=initial, fee_bps=fee_bps, slippage_bps=slippage_bps,
        latency_bars=latency_bars, hold_bars=hold_bars, risk_fraction=risk_fraction,
    )
    oos = run_backtest(
        test_bars, test_signals, initial=initial, fee_bps=fee_bps, slippage_bps=slippage_bps,
        latency_bars=latency_bars, hold_bars=hold_bars, risk_fraction=risk_fraction,
    )

    trade_returns = [
        float(t.pnl) / initial for t in full["trades"]
        if float(t.pnl) / initial > -1.0
    ]
    mc = monte_carlo_bootstrap(trade_returns, simulations=simulations, seed=seed) if trade_returns else None
    oos_positive_rate = 1.0 if oos["return"] > 0 else 0.0
    oos_loss_probability = mc.probability_of_loss if mc else 1.0
    robustness = anti_overfitting_score(
        train_return=float(train["return"]),
        oos_return=float(oos["return"]),
        oos_positive_rate=oos_positive_rate,
        oos_probability_of_loss=oos_loss_probability,
    )

    folds = walk_forward(
        bars,
        [b.ts for b in bars],
        train_size=max(10, split // 2),
        test_size=max(5, (len(bars) - split) // 2),
    )
    return {
        "full": _summary(full),
        "train": _summary(train),
        "oos": _summary(oos),
        "monte_carlo": {
            "simulations": mc.simulations,
            "p05_return": mc.p05_return,
            "median_return": mc.median_return,
            "p95_return": mc.p95_return,
            "probability_of_loss": mc.probability_of_loss,
            "p95_max_drawdown": mc.p95_max_drawdown,
        } if mc else None,
        "anti_overfitting": robustness,
        "walk_forward_folds": len(folds),
        "research_only": True,
        "live_orders": False,
    }
