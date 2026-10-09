"""Compare simple OHLC-executable strategy archetypes with chronological holdout.

Research only. Entries occur at the next bar open; no live orders are placed.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.storage import load_bars


def _ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = []
    value = float(values[0])
    for x in values:
        value = alpha * float(x) + (1.0 - alpha) * value
        out.append(value)
    return out


def _rsi(closes, period=14):
    out = [None] * len(closes)
    for i in range(period, len(closes)):
        changes = [closes[j] - closes[j - 1] for j in range(i - period + 1, i + 1)]
        gains = sum(max(x, 0.0) for x in changes) / period
        losses = sum(max(-x, 0.0) for x in changes) / period
        out[i] = 100.0 if losses == 0 else 100.0 - 100.0 / (1.0 + gains / losses)
    return out


def _atr(rows, period=14):
    tr = []
    for i, row in enumerate(rows):
        high, low, close = float(row.high), float(row.low), float(row.price)
        prev = float(rows[i - 1].price) if i else close
        tr.append(max(high - low, abs(high - prev), abs(low - prev)))
    out = [None] * len(rows)
    for i in range(period - 1, len(rows)):
        out[i] = sum(tr[i - period + 1:i + 1]) / period
    return out


def _features(rows):
    closes = [float(x.price) for x in rows]
    highs = [float(x.high) for x in rows]
    lows = [float(x.low) for x in rows]
    e20, e50 = _ema(closes, 20), _ema(closes, 50)
    rsi = _rsi(closes)
    atr = _atr(rows)
    momentum = [None] * len(rows)
    lower = [None] * len(rows)
    upper = [None] * len(rows)
    for i in range(len(rows)):
        if i >= 12 and closes[i - 12] > 0:
            momentum[i] = (closes[i] / closes[i - 12] - 1.0) * 100.0
        if i >= 19:
            window = closes[i - 19:i + 1]
            mean = statistics.fmean(window)
            sd = statistics.pstdev(window)
            lower[i], upper[i] = mean - 2.0 * sd, mean + 2.0 * sd
    trend = [0] * len(rows)
    for i in range(len(rows)):
        if e20[i] > e50[i] and closes[i] > e20[i]:
            trend[i] = 1
        elif e20[i] < e50[i] and closes[i] < e20[i]:
            trend[i] = -1
    return closes, highs, lows, e20, e50, rsi, atr, momentum, lower, upper, trend


def generate_signals(rows):
    """Create causal signals using only the current and earlier completed bars."""
    n = len(rows)
    closes, highs, lows, e20, e50, rsi, atr, momentum, lower, upper, trend = _features(rows)
    signals = {name: {} for name in (
        "ema_trend_flip", "momentum_threshold_cross", "breakout_20",
        "range_mean_reversion", "trend_pullback", "two_of_three_consensus"
    )}
    for i in range(60, n - 1):
        prev_trend = trend[i - 1]
        if trend[i] and trend[i] != prev_trend:
            signals["ema_trend_flip"][i] = trend[i]

        if momentum[i] is not None and momentum[i - 1] is not None:
            if momentum[i] >= 0.35 and momentum[i - 1] < 0.35 and closes[i] > e50[i]:
                signals["momentum_threshold_cross"][i] = 1
            elif momentum[i] <= -0.35 and momentum[i - 1] > -0.35 and closes[i] < e50[i]:
                signals["momentum_threshold_cross"][i] = -1

        if i >= 21:
            prior_high = max(highs[i - 20:i])
            prior_low = min(lows[i - 20:i])
            older_high = max(highs[i - 21:i - 1])
            older_low = min(lows[i - 21:i - 1])
            if closes[i] > prior_high and closes[i - 1] <= older_high:
                signals["breakout_20"][i] = 1
            elif closes[i] < prior_low and closes[i - 1] >= older_low:
                signals["breakout_20"][i] = -1

        if rsi[i] is not None and rsi[i - 1] is not None and lower[i] is not None and upper[i] is not None:
            range_regime = abs(e20[i] / e50[i] - 1.0) <= 0.005
            if range_regime and rsi[i] < 30 and closes[i] < lower[i] and (rsi[i - 1] >= 30 or closes[i - 1] >= lower[i - 1]):
                signals["range_mean_reversion"][i] = 1
            elif range_regime and rsi[i] > 70 and closes[i] > upper[i] and (rsi[i - 1] <= 70 or closes[i - 1] <= upper[i - 1]):
                signals["range_mean_reversion"][i] = -1

            if trend[i] == 1 and rsi[i - 1] < 40 <= rsi[i] and closes[i] > e50[i]:
                signals["trend_pullback"][i] = 1
            elif trend[i] == -1 and rsi[i - 1] > 60 >= rsi[i] and closes[i] < e50[i]:
                signals["trend_pullback"][i] = -1

        mom_vote = 1 if momentum[i] is not None and momentum[i] >= 0.35 and closes[i] > e50[i] else (
            -1 if momentum[i] is not None and momentum[i] <= -0.35 and closes[i] < e50[i] else 0
        )
        breakout_vote = signals["breakout_20"].get(i, 0)
        votes = [trend[i], mom_vote, breakout_vote]
        long_votes, short_votes = votes.count(1), votes.count(-1)
        consensus = 1 if long_votes >= 2 and long_votes > short_votes else (
            -1 if short_votes >= 2 and short_votes > long_votes else 0
        )
        if consensus and (i - 1 not in signals["two_of_three_consensus"] or signals["two_of_three_consensus"].get(i - 1) != consensus):
            signals["two_of_three_consensus"][i] = consensus
    return signals


def _metrics(trades, starting_capital):
    equity = float(starting_capital)
    peak = equity
    max_drawdown = 0.0
    wins, losses = [], []
    for trade in trades:
        pnl = equity * float(trade["net_return_pct"]) / 100.0
        trade["pnl_usd"] = round(pnl, 4)
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
        (wins if pnl > 0 else losses).append(pnl)
    n = len(trades)
    net = equity - starting_capital
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n, 4) if n else 0.0,
        "net_profit_usd": round(net, 4),
        "return_pct": round(net / starting_capital * 100.0, 4) if starting_capital else 0.0,
        "expectancy_usd": round(net / n, 4) if n else 0.0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 4) if losses else ("infinite" if wins else None),
        "max_drawdown_pct": round(max_drawdown, 4),
        "starting_capital_usd": starting_capital,
        "ending_equity_usd": round(equity, 4),
    }


def simulate(rows, signals, *, target_pct, stop_pct, cost_pct, max_hold=12, cooldown=3, capital=500.0):
    trades = []
    i = 60
    next_allowed = 60
    while i < len(rows) - 1:
        direction = signals.get(i, 0)
        if not direction or i < next_allowed:
            i += 1
            continue
        entry_idx = i + 1
        entry = float(rows[entry_idx].open)
        if not math.isfinite(entry) or entry <= 0:
            i += 1
            continue
        is_long = direction == 1
        target = entry * (1.0 + target_pct / 100.0) if is_long else entry * (1.0 - target_pct / 100.0)
        stop = entry * (1.0 - stop_pct / 100.0) if is_long else entry * (1.0 + stop_pct / 100.0)
        end_idx = min(entry_idx + max_hold - 1, len(rows) - 1)
        exit_idx, exit_price, reason = end_idx, float(rows[end_idx].price), "TIME_EXIT"
        for j in range(entry_idx, end_idx + 1):
            row = rows[j]
            op, high, low = float(row.open), float(row.high), float(row.low)
            if is_long:
                if op <= stop or low <= stop:
                    exit_idx, exit_price, reason = j, (min(op, stop) if op <= stop else stop), "STOP"
                    break
                if high >= target:
                    exit_idx, exit_price, reason = j, target, "TARGET"
                    break
            else:
                if op >= stop or high >= stop:
                    exit_idx, exit_price, reason = j, (max(op, stop) if op >= stop else stop), "STOP"
                    break
                if low <= target:
                    exit_idx, exit_price, reason = j, target, "TARGET"
                    break
        gross = ((exit_price / entry) - 1.0) * 100.0 if is_long else ((entry / exit_price) - 1.0) * 100.0
        trades.append({
            "signal_index": i, "signal_ts": int(rows[i].ts),
            "entry_ts": int(rows[entry_idx].ts), "exit_ts": int(rows[exit_idx].ts),
            "direction": "LONG" if is_long else "SHORT",
            "entry_price": round(entry, 8), "exit_price": round(exit_price, 8),
            "target_pct": target_pct, "stop_pct": stop_pct, "cost_pct": cost_pct,
            "gross_return_pct": round(gross, 6), "net_return_pct": round(gross - cost_pct, 6),
            "exit_reason": reason,
        })
        next_allowed = exit_idx + cooldown + 1
        i = next_allowed
    return trades


def backtest(rows, *, cost_levels=(0.35, 0.50), target_stop_profiles=((1.15, 0.50), (2.35, 0.75)),
             max_hold=12, cooldown=3, capital=500.0):
    if len(rows) < 300:
        return {"status": "insufficient_data", "bars": len(rows), "trade_ready": False,
                "research_only": True, "live_orders": False}
    if any(getattr(row, "open", None) is None or getattr(row, "high", None) is None or getattr(row, "low", None) is None for row in rows):
        return {"status": "ohlc_unavailable", "bars": len(rows), "trade_ready": False,
                "research_only": True, "live_orders": False}
    signals_by_strategy = generate_signals(rows)
    holdout_ts = int(rows[int(len(rows) * 0.60)].ts)
    results = []
    for strategy, signals in signals_by_strategy.items():
        for target_pct, stop_pct in target_stop_profiles:
            for cost_pct in cost_levels:
                trades = simulate(rows, signals, target_pct=target_pct, stop_pct=stop_pct,
                                  cost_pct=cost_pct, max_hold=max_hold, cooldown=cooldown, capital=capital)
                dev = [dict(t) for t in trades if t["signal_ts"] < holdout_ts]
                holdout = [dict(t) for t in trades if t["signal_ts"] >= holdout_ts]
                results.append({
                    "strategy": strategy, "target_pct": target_pct, "stop_pct": stop_pct,
                    "round_trip_cost_pct": cost_pct,
                    "development": _metrics(dev, capital),
                    "holdout_oos": _metrics(holdout, capital),
                    "full_walk_forward": _metrics([dict(t) for t in trades], capital),
                    "trades": trades,
                })
    return {
        "status": "ok", "symbol": rows[-1].symbol, "bars": len(rows),
        "first_ts": int(rows[0].ts), "last_ts": int(rows[-1].ts),
        "holdout_start_ts": holdout_ts, "max_hold_bars": max_hold, "cooldown_bars": cooldown,
        "capital_usd": capital, "buy_hold_return_pct": round((float(rows[-1].price) / float(rows[0].price) - 1) * 100, 4),
        "results": results, "trade_ready": False,
        "trade_readiness_reason": "Exploratory archetype comparison only; no strategy is approved for live trading.",
        "research_only": True, "live_orders": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--capital", type=float, default=500.0)
    parser.add_argument("--max-hold", type=int, default=12)
    parser.add_argument("--cooldown", type=int, default=3)
    args = parser.parse_args()
    rows = load_bars(Path(args.input))
    report = backtest(rows, capital=args.capital, max_hold=args.max_hold, cooldown=args.cooldown)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    compact = {k: v for k, v in report.items() if k != "results"}
    compact["results"] = [{
        "strategy": x["strategy"], "target_pct": x["target_pct"], "stop_pct": x["stop_pct"],
        "round_trip_cost_pct": x["round_trip_cost_pct"],
        "development": x["development"], "holdout_oos": x["holdout_oos"],
        "full_walk_forward": x["full_walk_forward"],
    } for x in report.get("results", [])]
    print(json.dumps(compact, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
