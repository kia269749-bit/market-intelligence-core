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
    pnls = [t.pnl for t in trades]  # net of modeled execution costs
    gross_pnls = [t.pnl + t.cost for t in trades]
    net_winners = [p for p in pnls if p > 0]
    net_losers = [p for p in pnls if p < 0]
    gross_profit = sum(p for p in gross_pnls if p > 0)
    gross_loss = abs(sum(p for p in gross_pnls if p < 0))
    net_profit = sum(pnls)
    net_loss = abs(sum(net_losers))
    return {
        "initial": initial,
        "final": final,
        "return": final / initial - 1.0,
        "max_drawdown": max_drawdown,
        "trades_count": len(trades),
        "wins": len(net_winners),
        "losses": len(net_losers),
        "win_rate": len(net_winners) / len(pnls) if pnls else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit_usd": net_profit,
        "net_loss_usd": net_loss,
        "profit_factor": sum(net_winners) / net_loss if net_loss else (float("inf") if net_winners else 0.0),
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
    fee_bps=None,
    slippage_bps=None,
    latency_bars=None,
    hold_bars=1,
    risk_fraction=.10,
):
    """Backtest signals chronologically with fee, slippage and latency modeling."""
    if len(bars) != len(signals):
        raise ValueError("bars and signals must have equal length")
    from .central_config import load_settings
    settings = load_settings()
    fee_bps = settings.taker_fee_bps if fee_bps is None else float(fee_bps)
    slippage_bps = settings.slippage_bps if slippage_bps is None else float(slippage_bps)
    spread_bps = settings.spread_bps
    impact_bps = settings.impact_bps
    latency_bars = settings.latency_bars if latency_bars is None else int(latency_bars)
    _validate_config(initial, fee_bps, slippage_bps, latency_bars, hold_bars, risk_fraction)
    if spread_bps < 0 or impact_bps < 0:
        raise ValueError("spread_bps and impact_bps must be non-negative")

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
        # Model spread, slippage, and impact on both entry and exit fills.
        # Fee is charged on executed notional at both ends. Trade.cost reports
        # all friction while pnl already includes the fill-price effect.
        friction_bps = spread_bps + slippage_bps + impact_bps
        friction = friction_bps / 10000.0
        base_entry = bars[entry_i].price
        base_exit = bars[exit_i].price
        entry = base_entry * (1 + direction * friction)
        exitp = base_exit * (1 - direction * friction)
        qty = equity * risk_fraction / max(entry, 1e-12)
        gross = direction * (exitp - entry) * qty
        fee_cost = (abs(entry * qty) + abs(exitp * qty)) * fee_bps / 10000.0
        market_friction_cost = (abs(base_entry * qty) + abs(base_exit * qty)) * friction_bps / 10000.0
        cost = fee_cost + market_friction_cost
        pnl = gross - fee_cost
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
