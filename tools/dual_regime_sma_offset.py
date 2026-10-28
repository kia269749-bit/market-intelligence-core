"""Isolated research simulator for Dual Regime SMA Offset v1.

Binance Spot OHLCV proxy only. No live execution. Signals use completed bars;
orders are simulated at the next bar open. Missing/unmatched breadth inputs fail closed.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from mi_core.storage import load_bars

COSTS_PCT = (0.24, 0.12, 0.04)
UNIVERSE = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "TRXUSDT", "LINKUSDT", "AVAXUSDT",
    "DOTUSDT", "LTCUSDT", "BCHUSDT", "UNIUSDT", "NEARUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "FILUSDT",
)
CANDIDATE_OFFSETS = (0.03, 0.05, 0.07)
BAR_MS = 4 * 60 * 60 * 1000


def sma(values, period):
    out = [math.nan] * len(values)
    for i in range(period - 1, len(values)):
        chunk = values[i - period + 1:i + 1]
        if all(math.isfinite(v) for v in chunk):
            out[i] = sum(chunk) / period
    return out


def atr(rows, period=14):
    """ATR at close i uses only OHLC values through completed bar i."""
    tr = []
    for i, row in enumerate(rows):
        high, low, close = float(row.high), float(row.low), float(row.price)
        prev_close = float(rows[i - 1].price) if i else close
        tr.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    out = [math.nan] * len(rows)
    if len(rows) >= period:
        out[period - 1] = sum(tr[:period]) / period
        for i in range(period, len(rows)):
            out[i] = ((period - 1) * out[i - 1] + tr[i]) / period
    return out


def _series(rows, attr):
    return [float(getattr(r, attr)) for r in rows]


def validate_contiguous_timestamps(timestamps, interval_ms=BAR_MS):
    """Reject missing aligned bars instead of compressing time across data gaps."""
    for a, b in zip(timestamps, timestamps[1:]):
        if int(b) - int(a) != interval_ms:
            raise ValueError(f"non-contiguous aligned timestamps: gap {int(b) - int(a)} ms after {int(a)}")


def align_universe(bars_by_symbol, universe=UNIVERSE):
    """Return timestamps where every fixed universe member has a completed bar."""
    indexed = {}
    for symbol in universe:
        rows = bars_by_symbol.get(symbol, [])
        indexed[symbol] = {int(r.ts): r for r in rows}
    common = set.intersection(*(set(v) for v in indexed.values())) if indexed else set()
    timestamps = sorted(common)
    return timestamps, indexed


def build_regime(bars_by_symbol, timestamps, indexed, universe=UNIVERSE):
    btc_rows = [indexed["BTCUSDT"][t] for t in timestamps]
    btc_sma = sma(_series(btc_rows, "price"), 200)
    sma50_by_symbol = {}
    for symbol in universe:
        rows = [indexed[symbol][t] for t in timestamps]
        sma50_by_symbol[symbol] = sma(_series(rows, "price"), 50)
    regime = {}
    breadth = {}
    for i, ts in enumerate(timestamps):
        if not math.isfinite(btc_sma[i]) or not (float(btc_rows[i].price) > btc_sma[i]):
            regime[ts] = False
            breadth[ts] = math.nan
            continue
        valid = [sma50_by_symbol[s][i] for s in universe]
        if not all(math.isfinite(x) for x in valid):
            regime[ts] = False
            breadth[ts] = math.nan
            continue
        fraction = sum(float(indexed[s][ts].price) > sma50_by_symbol[s][i] for s in universe) / len(universe)
        breadth[ts] = fraction
        regime[ts] = fraction >= 0.5
    return regime, breadth


def build_candidate_signals(rows, regime_by_ts, offset_pct=0.05):
    """Close-time long/flat signals; one entry per armed pullback."""
    closes = _series(rows, "price")
    highs = _series(rows, "high")
    lows = _series(rows, "low")
    s20, s50 = sma(closes, 20), sma(closes, 50)
    a14 = atr(rows, 14)
    n = len(rows)
    entry = [False] * n
    regime = [bool(regime_by_ts.get(int(r.ts), False)) for r in rows]
    armed = False
    for i in range(1, n):
        valid = regime[i] and math.isfinite(s20[i]) and math.isfinite(s50[i]) and s20[i] > s50[i]
        in_pullback_band = valid and closes[i] <= s20[i] and closes[i] >= s20[i] * (1 - offset_pct) and closes[i] > s50[i]
        if not valid:
            armed = False
            continue
        if in_pullback_band:
            armed = True
        reclaim = armed and closes[i - 1] <= s20[i - 1] and closes[i] > s20[i]
        if reclaim:
            entry[i] = True
            armed = False
    return {"entry": entry, "regime": regime, "sma20": s20, "sma50": s50, "atr": a14}


def build_ema_signals(rows):
    closes = _series(rows, "price")
    e12, e26 = _ema(closes, 12), _ema(closes, 26)
    return [math.isfinite(a) and math.isfinite(b) and a > b for a, b in zip(e12, e26)]


def _ema(values, period):
    out = [math.nan] * len(values)
    if len(values) < period:
        return out
    seed = values[:period]
    if all(math.isfinite(v) for v in seed):
        out[period - 1] = sum(seed) / period
    alpha = 2.0 / (period + 1)
    for i in range(period, len(values)):
        if math.isfinite(values[i]) and math.isfinite(out[i - 1]):
            out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def simulate(rows, signals, *, cost_pct=0.24, initial_equity=500.0,
             risk_fraction=0.01, use_risk=True, use_stops=True, use_trailing=True,
             use_time_exit=True, circuit_breaker=True):
    """Causal single-asset spot simulation; no leverage; returns detailed metrics."""
    if cost_pct not in COSTS_PCT:
        raise ValueError("cost_pct must be one of the preregistered sensitivity scenarios")
    if len(rows) != len(signals.get("regime", signals.get("entry", signals))) if isinstance(signals, dict) else len(rows) != len(signals):
        raise ValueError("rows and signals must have equal length")
    if isinstance(signals, dict):
        entries, regime, atr_values = signals["entry"], signals["regime"], signals["atr"]
        target_state = signals.get("target")
    else:
        entries, regime, atr_values = list(signals), [True] * len(rows), atr(rows, 14)
        target_state = entries
    if len(entries) != len(rows) or len(regime) != len(rows):
        raise ValueError("signals length mismatch")
    cost_rate = cost_pct / 100.0
    equity = float(initial_equity)
    peak = equity
    position = None
    trades = []
    equity_path = []
    breaker = False
    rolling_equity = []
    pending_exit = None
    for i, row in enumerate(rows):
        exited_this_bar = False
        ts = int(row.ts)
        op, hi, lo, close = map(float, (row.open, row.high, row.low, row.price))
        # Pending close-time exits execute at this bar's open.
        if position and pending_exit:
            exit_price = op
            gross = position["qty"] * (exit_price - position["entry"])
            costs = position["qty"] * (position["entry"] + exit_price) * cost_rate / 2
            pnl = gross - costs
            equity += pnl
            trades.append({"entry_ts": position["entry_ts"], "exit_ts": ts, "entry": position["entry"],
                           "exit": exit_price, "qty": position["qty"], "gross_pnl": gross,
                           "cost": costs, "net_pnl": pnl, "reason": pending_exit})
            position, pending_exit = None, None
            exited_this_bar = True
        # A stop already known before this bar is evaluated conservatively against this bar's OHLC.
        if position and use_stops:
            stop = position["stop"]
            if op <= stop or lo <= stop:
                exit_price = op if op <= stop else stop
                gross = position["qty"] * (exit_price - position["entry"])
                costs = position["qty"] * (position["entry"] + exit_price) * cost_rate / 2
                pnl = gross - costs
                equity += pnl
                trades.append({"entry_ts": position["entry_ts"], "exit_ts": ts, "entry": position["entry"],
                               "exit": exit_price, "qty": position["qty"], "gross_pnl": gross,
                               "cost": costs, "net_pnl": pnl, "reason": "stop"})
                position = None
                exited_this_bar = True
        # Update rolling 30-day equity using marked-to-market equity at close.
        marked = equity + (position["qty"] * (close - position["entry"]) if position else 0.0)
        rolling_equity.append((ts, marked))
        cutoff = ts - 30 * 24 * 60 * 60 * 1000
        rolling_equity = [(t, e) for t, e in rolling_equity if t >= cutoff]
        if circuit_breaker and rolling_equity:
            rolling_peak = max(e for _, e in rolling_equity)
            if marked <= rolling_peak * 0.80:
                breaker = True
        if position:
            position["bars"] += 1
            position["highest_high"] = max(position["highest_high"], hi)
            # Stops calculated at this close become active only from the next bar.
            av = atr_values[i] if i < len(atr_values) else math.nan
            if use_trailing and math.isfinite(av):
                position["stop"] = max(position["stop"], position["highest_high"] - 2 * av)
            if use_time_exit and position["bars"] >= 10 and close < position["entry"] * 1.01:
                pending_exit = "time_exit"
            elif not regime[i]:
                pending_exit = "regime_exit"
            elif target_state is not None and not target_state[i]:
                pending_exit = "signal_exit"
        # Signal at prior completed close, execute at current open. First bar cannot enter.
        if position is None and not exited_this_bar and not breaker and i > 0 and entries[i - 1] and regime[i - 1]:
            av = atr_values[i - 1] if i - 1 < len(atr_values) else math.nan
            if op <= 0 or (use_risk and (not math.isfinite(av) or av <= 0)):
                equity_path.append({"ts": ts, "equity": equity})
                continue
            stop = op - 2 * av if math.isfinite(av) and av > 0 else 0.0
            risk_per_unit = (op - stop) + op * cost_rate if stop > 0 else op * cost_rate
            qty = min(equity / op, equity * risk_fraction / risk_per_unit) if use_risk else equity / op
            if qty > 0 and (not use_stops or stop > 0):
                position = {"entry_ts": ts, "entry": op, "qty": qty, "stop": stop,
                            "highest_high": op, "bars": 0}
                # The entry bar is active immediately after the next-open fill.
                # If its low crosses the initial stop, assume a conservative stop fill.
                if use_stops and lo <= stop:
                    exit_price = stop
                    gross = qty * (exit_price - op)
                    costs = qty * (op + exit_price) * cost_rate / 2
                    pnl = gross - costs
                    equity += pnl
                    trades.append({"entry_ts": ts, "exit_ts": ts, "entry": op, "exit": exit_price,
                                   "qty": qty, "gross_pnl": gross, "cost": costs,
                                   "net_pnl": pnl, "reason": "entry_bar_stop"})
                    position = None
                    exited_this_bar = True
                elif not regime[i]:
                    pending_exit = "regime_exit"
        equity_path.append({"ts": ts, "equity": marked})
    # Close any remaining position at final close, explicitly marked as end-of-window exit.
    if position and rows:
        row = rows[-1]
        exit_price = float(row.price)
        gross = position["qty"] * (exit_price - position["entry"])
        costs = position["qty"] * (position["entry"] + exit_price) * cost_rate / 2
        pnl = gross - costs
        equity += pnl
        trades.append({"entry_ts": position["entry_ts"], "exit_ts": int(row.ts), "entry": position["entry"],
                       "exit": exit_price, "qty": position["qty"], "gross_pnl": gross,
                       "cost": costs, "net_pnl": pnl, "reason": "window_end"})
    pnls = [t["net_pnl"] for t in trades]
    wins = sum(p > 0 for p in pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    eqs = [p["equity"] for p in equity_path]
    running_peak = initial_equity
    max_dd = 0.0
    for e in eqs:
        running_peak = max(running_peak, e)
        if running_peak:
            max_dd = max(max_dd, (running_peak - e) / running_peak)
    returns = []
    for a, b in zip(eqs, eqs[1:]):
        if a > 0:
            returns.append(b / a - 1)
    sd = pstdev(returns) if len(returns) > 1 else 0.0
    sharpe = (mean(returns) / sd * math.sqrt(6 * 365.25) if sd else 0.0)  # 4h bars/year = 6*365.25
    return {
        "initial_equity_usd": initial_equity, "final_equity_usd": round(equity, 4),
        "net_pnl_usd": round(equity - initial_equity, 4),
        "net_return_pct": round((equity / initial_equity - 1) * 100, 4),
        "max_drawdown_pct": round(max_dd * 100, 4), "sharpe_annualized_approx": round(sharpe, 4),
        "trade_count": len(trades), "win_rate_pct": round(wins / len(trades) * 100, 4) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (None if not gross_profit else "infinite"),
        "expectancy_usd_per_trade": round(mean(pnls), 4) if pnls else None,
        "gross_pnl_usd": round(sum(t["gross_pnl"] for t in trades), 4),
        "cost_total_usd": round(sum(t["cost"] for t in trades), 4),
        "circuit_breaker_triggered": breaker, "trades": trades,
    }


def random_matched_signals(rows, count, seed):
    """One seeded post-hoc matched comparator; not used as a standalone p-value."""
    eligible = list(range(1, max(1, len(rows) - 1)))
    rng = random.Random(seed)
    count = min(max(0, count), len(eligible))
    points = set(rng.sample(eligible, count)) if count else set()
    holding = False
    out = []
    for i in range(len(rows)):
        if i in points:
            holding = not holding
        out.append(holding)
    return out


def run_walk_forward(bars_by_symbol, *, cost_pct=0.24, offsets=CANDIDATE_OFFSETS):
    """Non-overlapping 3-month OOS windows with 12-month prior context; exploratory only."""
    timestamps, indexed = align_universe(bars_by_symbol)
    validate_contiguous_timestamps(timestamps)
    if len(timestamps) < 200 + 50:
        raise ValueError("insufficient exact-aligned 20-asset bars for regime warm-up")
    regime, breadth = build_regime(bars_by_symbol, timestamps, indexed)
    # Common timestamp index ensures every asset and BTC regime use same completed bar.
    results = {}
    interval = BAR_MS
    window_bars = int(90 * 24 * 60 * 60 * 1000 / interval)
    warmup_bars = int(365 * 24 * 60 * 60 * 1000 / interval)
    first = max(250, warmup_bars)
    for symbol in ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"):
        rows = [indexed[symbol][t] for t in timestamps]
        if len(rows) <= first + window_bars:
            results[symbol] = {"status": "insufficient_data", "bars": len(rows)}
            continue
        per_offset = {}
        for offset in offsets:
            sig = build_candidate_signals(rows, regime, offset_pct=offset)
            windows = []
            start = first
            while start < len(rows):
                end = min(len(rows), start + window_bars)
                sub_rows = rows[start:end]
                sub_sig = {k: v[start:end] for k, v in sig.items()}
                candidate = simulate(sub_rows, sub_sig, cost_pct=cost_pct)
                simple_candidate = simulate(sub_rows, sub_sig, cost_pct=cost_pct,
                                            use_risk=False, use_stops=False, use_trailing=False,
                                            use_time_exit=False, circuit_breaker=False)
                # Baselines use identical OOS bars and next-open execution.
                ema_all = build_ema_signals(rows)
                ema_result = simulate(sub_rows, ema_all[start:end], cost_pct=cost_pct,
                                      use_risk=True, use_stops=True, use_trailing=False,
                                      use_time_exit=False, circuit_breaker=True)
                buyhold_result = simulate(sub_rows, [True] * len(sub_rows), cost_pct=cost_pct,
                                          use_risk=False, use_stops=False, use_trailing=False,
                                          use_time_exit=False, circuit_breaker=False)
                random_results = []
                transition_count = min(2 * candidate["trade_count"], max(0, len(sub_rows) - 2))
                for seed in range(1000):
                    rand_target = random_matched_signals(sub_rows, transition_count, seed + 1729)
                    rand_entries = [bool(rand_target[i] and (i == 0 or not rand_target[i - 1])) for i in range(len(rand_target))]
                    rand_payload = {"entry": rand_entries, "target": rand_target,
                                    "regime": sub_sig["regime"], "atr": sub_sig["atr"]}
                    random_results.append(simulate(sub_rows, rand_payload, cost_pct=cost_pct)["net_return_pct"])
                random_returns = sorted(random_results)
                p_emp = (1 + sum(x >= candidate["net_return_pct"] for x in random_returns)) / (len(random_returns) + 1)
                windows.append({
                    "start_ts": int(sub_rows[0].ts), "end_ts": int(sub_rows[-1].ts),
                    "candidate": {k: v for k, v in candidate.items() if k != "trades"},
                    "dual_regime_sma_offset_simple": {k: v for k, v in simple_candidate.items() if k != "trades"},
                    "ema12_26": {k: v for k, v in ema_result.items() if k != "trades"},
                    "buy_and_hold": {k: v for k, v in buyhold_result.items() if k != "trades"},
                    "random_1000_return_pct_p05_median_p95": {
                        "p05": random_returns[49], "median": random_returns[499], "p95": random_returns[949]},
                    "random_empirical_p_value_one_sided": round(p_emp, 5),
                })
                start = end
            per_offset[str(offset)] = windows
        results[symbol] = {"status": "exploratory", "bars": len(rows), "offset_results": per_offset}
    return {
        "protocol_id": "dual-regime-sma-offset-v1",
        "research_only": True, "live_orders": False,
        "data_basis": "Binance Spot OHLCV proxy; not Hyperliquid Perpetuals",
        "breadth_universe": list(UNIVERSE),
        "cost_pct_round_trip": cost_pct,
        "sensitivity_rates_pct": list(COSTS_PCT),
        "window_policy": {"context_bars_approx_12m": warmup_bars, "oos_bars_approx_3m": window_bars, "non_overlapping": True},
        "common_aligned_timestamps": len(timestamps),
        "first_timestamp": timestamps[0], "last_timestamp": timestamps[-1],
        "breadth_valid_fraction": sum(math.isfinite(v) for v in breadth.values()) / len(breadth) if breadth else 0,
        "limitations": [
            "Historical data may have been previously inspected; this WFA is exploratory unless exposure audit proves otherwise.",
            "Random comparator uses 1,000 seeded paths and matched position-change count, but p-values are not adjusted for candidate-family multiple testing in this prototype.",
            "PBO/CSCV is not calculated until independent partitions and candidate-family validity are reviewed.",
            "Slippage, order-book depth, funding, latency and partial fills are not represented by Binance Spot OHLCV.",
            "Portfolio-level equal-weight aggregation and block-bootstrap confidence intervals require separate review before any acceptance claim."
        ],
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Directory with SYMBOL_4h.jsonl files for the full 20-asset universe")
    parser.add_argument("--out", required=True)
    parser.add_argument("--costs", default="0.24", help="Run one pre-registered rate per invocation; primary is 0.24")
    args = parser.parse_args()
    cost = float(args.costs)
    if cost not in COSTS_PCT:
        raise SystemExit(f"--costs must be one of {COSTS_PCT}")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    by_symbol = {}
    for symbol in UNIVERSE:
        path = Path(args.data_dir) / f"{symbol}_4h.jsonl"
        if not path.exists():
            raise SystemExit(f"missing required breadth data file: {path}")
        rows = [r for r in load_bars(path) if int(r.ts) + BAR_MS <= now_ms]
        by_symbol[symbol] = rows
    report = run_walk_forward(by_symbol, cost_pct=cost)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"out": str(out), "cost_pct_round_trip": cost, "aligned_timestamps": report["common_aligned_timestamps"],
                      "data_basis": report["data_basis"], "research_only": True, "live_orders": False}, indent=2))


if __name__ == "__main__":
    main()
