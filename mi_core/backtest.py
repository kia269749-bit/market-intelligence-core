"""Research-only event backtest with explicit execution costs and diagnostics."""
from __future__ import annotations

from .models import Trade


def _validate_config(initial, fee_bps, slippage_bps, latency_bars, hold_bars, risk_fraction):
    if initial <= 0:
        raise ValueError("initial must be positive")
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError("fee_bps and slippage_bps must be non-negative")
    if latency_bars < 0 or hold_bars < 1:
        raise ValueError("latency_bars must be non-negative and hold_bars positive")
    if not 0 < risk_fraction <= 1:
        raise ValueError("risk_fraction must be in (0, 1]")


def _metrics(trades, initial, final, max_drawdown):
    pnls = [t.pnl for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    return {
        "initial": initial,
        "final": final,
        "return": final / initial - 1.0,
        "max_drawdown": max_drawdown,
        "trades_count": len(trades),
        "wins": len(winners),
        "losses": len(losers),
        "win_rate": len(winners) / len(pnls) if pnls else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
        "expectancy": sum(pnls) / len(pnls) if pnls else 0.0,
        "cost_total": sum(t.cost for t in trades),
        "research_only": True,
        "live_orders": False,
        "trades": trades,
    }


def run(
    bars,
    signals,
    initial=10000.0,
    fee_bps=5.0,
    slippage_bps=3.0,
    latency_bars=1,
    hold_bars=1,
    risk_fraction=.10,
):
    """Backtest signals chronologically with fee, slippage and latency modeling."""
    if len(bars) != len(signals):
        raise ValueError("bars and signals must have equal length")
    _validate_config(initial, fee_bps, slippage_bps, latency_bars, hold_bars, risk_fraction)

    equity = initial
    peak = initial
    max_dd = 0.0
    trades = []
    i = 0

    while i < len(bars):
        s = signals[i]
        if s.side == "FLAT":
            i += 1
            continue

        entry_i = i + latency_bars
        exit_i = min(len(bars) - 1, entry_i + hold_bars)
        if entry_i >= len(bars) or exit_i <= entry_i:
            break

        direction = 1 if s.side == "LONG" else -1
        slip = slippage_bps / 10000.0
        entry = bars[entry_i].price * (1 + direction * slip)
        exitp = bars[exit_i].price * (1 - direction * slip)
        qty = equity * risk_fraction / max(entry, 1e-12)
        gross = direction * (exitp - entry) * qty
        cost = (abs(entry * qty) + abs(exitp * qty)) * fee_bps / 10000.0
        pnl = gross - cost
        equity += pnl

        trades.append(
            Trade(
                bars[entry_i].ts, bars[exit_i].ts, s.symbol, s.side,
                entry, exitp, qty, pnl, cost, "signal",
            )
        )
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        i = exit_i + 1

    return _metrics(trades, initial, equity, max_dd)
