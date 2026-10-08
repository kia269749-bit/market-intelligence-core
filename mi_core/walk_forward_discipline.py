"""Walk-forward evaluation for arena-inspired entry discipline.

The rules are fixed before each test window. No OOS result is used to tune the
preceding test window. Research-only and cost-aware.
"""
from __future__ import annotations

from .arena_discipline_backtest import _base_signals, _patience_filter, _confirmation_filter
from .backtest import run


def _arm_signals(bars, threshold, arm):
    base = _base_signals(bars, threshold)
    if arm == "baseline":
        return base
    if arm == "patience":
        return [_patience_filter(s) for s in base]
    if arm == "confirmation":
        return _confirmation_filter(base)
    raise ValueError("unknown arm")


def walk_forward_compare(
    bars,
    *,
    train_bars: int = 500,
    test_bars: int = 150,
    entry_threshold: float = .60,
    initial: float = 500.0,
    fee_bps: float = 17.5,
    slippage_bps: float = 10.0,
    latency_bars: int = 1,
    hold_bars: int = 6,
    risk_fraction: float = .10,
) -> dict:
    if train_bars < 21 or test_bars < 1:
        raise ValueError("train_bars must be >=21 and test_bars must be positive")
    if len(bars) < train_bars + test_bars:
        return {"available": False, "reason": "insufficient_history", "samples": len(bars)}

    arms = ("baseline", "patience", "confirmation")
    windows = []
    i = 0
    while i + train_bars + test_bars <= len(bars):
        train = bars[i:i + train_bars]
        test = bars[i + train_bars:i + train_bars + test_bars]
        row = {"start": i, "train_bars": train_bars, "test_bars": test_bars, "arms": {}}
        for arm in arms:
            # Train window is deliberately used only to establish the frozen
            # rule context. The actual score is then evaluated on unseen bars.
            train_result = run(
                train, _arm_signals(train, entry_threshold, arm),
                initial=initial, fee_bps=fee_bps, slippage_bps=slippage_bps,
                latency_bars=latency_bars, hold_bars=hold_bars,
                risk_fraction=risk_fraction,
            )
            test_result = run(
                test, _arm_signals(test, entry_threshold, arm),
                initial=initial, fee_bps=fee_bps, slippage_bps=slippage_bps,
                latency_bars=latency_bars, hold_bars=hold_bars,
                risk_fraction=risk_fraction,
            )
            row["arms"][arm] = {
                "train": {
                    "trades": train_result["trades_count"],
                    "return_pct": round(train_result["return"] * 100, 4),
                    "profit_factor": round(train_result["profit_factor"], 4) if train_result["profit_factor"] != float("inf") else "inf",
                },
                "oos": {
                    "trades": test_result["trades_count"],
                    "return_pct": round(test_result["return"] * 100, 4),
                    "net_profit": round(test_result["final"] - test_result["initial"], 4),
                    "win_rate": round(test_result["win_rate"], 4),
                    "profit_factor": round(test_result["profit_factor"], 4) if test_result["profit_factor"] != float("inf") else "inf",
                    "expectancy": round(test_result["expectancy"], 4),
                    "max_drawdown_pct": round(test_result["max_drawdown"] * 100, 4),
                    "cost_total": round(test_result["cost_total"], 4),
                },
            }
        windows.append(row)
        i += test_bars

    aggregate = {}
    for arm in arms:
        rows = [w["arms"][arm]["oos"] for w in windows]
        trades = sum(r["trades"] for r in rows)
        profit = sum(r["net_profit"] for r in rows)
        positive_windows = sum(r["net_profit"] > 0 for r in rows)
        aggregate[arm] = {
            "windows": len(rows),
            "oos_trades": trades,
            "oos_net_profit_sum": round(profit, 4),
            "positive_oos_window_rate": round(positive_windows / len(rows), 4) if rows else 0.0,
            "mean_oos_return_pct": round(sum(r["return_pct"] for r in rows) / len(rows), 4) if rows else 0.0,
            "mean_oos_profit_factor": round(
                sum(r["profit_factor"] for r in rows if isinstance(r["profit_factor"], (int, float))) /
                max(1, sum(isinstance(r["profit_factor"], (int, float)) for r in rows)), 4
            ) if rows else 0.0,
            "mean_oos_expectancy": round(sum(r["expectancy"] for r in rows) / len(rows), 4) if rows else 0.0,
        }

    return {
        "available": True,
        "windows": windows,
        "aggregate": aggregate,
        "policy": "fixed_rules_per_window; no OOS tuning",
        "cost_model": {"fee_bps": fee_bps, "slippage_bps": slippage_bps,
                       "latency_bars": latency_bars, "hold_bars": hold_bars},
        "research_only": True,
        "live_orders": False,
    }
