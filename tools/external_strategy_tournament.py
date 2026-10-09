"""External strategy benchmark tournament on real OHLC data.

Fixed, published strategy families; no parameter optimization. Research only.
Signals use completed closes and are delayed before execution. Costs are charged
on position changes using a fixed round-trip cost assumption.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.storage import load_bars


STRATEGY_NAMES = (
    "buy_and_hold",
    "sma200_trend_filter",
    "ema20_50_trend",
    "momentum_7d_long_short",
    "donchian20_10_breakout",
    "rsi14_mean_reversion",
)


def _float_series(rows, key):
    out = []
    for row in rows:
        value = getattr(row, key, None)
        if value is None:
            value = getattr(row, "price", None) if key == "close" else None
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = math.nan
        out.append(value if math.isfinite(value) and value > 0 else math.nan)
    return out


def _sma(values, window):
    result = [math.nan] * len(values)
    for i in range(window - 1, len(values)):
        chunk = values[i - window + 1:i + 1]
        if all(math.isfinite(x) for x in chunk):
            result[i] = sum(chunk) / window
    return result


def _ema(values, window):
    result = [math.nan] * len(values)
    alpha = 2.0 / (window + 1.0)
    valid = [i for i, x in enumerate(values) if math.isfinite(x)]
    if len(valid) < window:
        return result
    first = valid[window - 1]
    seed = values[first - window + 1:first + 1]
    if not all(math.isfinite(x) for x in seed):
        return result
    result[first] = sum(seed) / window
    for i in range(first + 1, len(values)):
        if math.isfinite(values[i]):
            result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]
    return result


def _rsi(values, window=14):
    result = [math.nan] * len(values)
    if len(values) <= window:
        return result
    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window
    def value(g, l):
        if l == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / l)
    result[window] = value(avg_gain, avg_loss)
    for i in range(window + 1, len(values)):
        avg_gain = ((window - 1) * avg_gain + gains[i - 1]) / window
        avg_loss = ((window - 1) * avg_loss + losses[i - 1]) / window
        result[i] = value(avg_gain, avg_loss)
    return result


def build_signals(rows):
    """Return fixed-rule close-time target positions, each in {-1, 0, +1}."""
    closes = _float_series(rows, "price")
    highs = _float_series(rows, "high")
    lows = _float_series(rows, "low")
    n = len(rows)
    if n < 210:
        raise ValueError("At least 210 daily OHLC bars are required for the common 200-bar warm-up.")
    sma200 = _sma(closes, 200)
    ema20, ema50 = _ema(closes, 20), _ema(closes, 50)
    rsi14 = _rsi(closes, 14)

    signals = {name: [0.0] * n for name in STRATEGY_NAMES}
    for i in range(n):
        signals["buy_and_hold"][i] = 1.0
        if math.isfinite(sma200[i]):
            signals["sma200_trend_filter"][i] = 1.0 if closes[i] > sma200[i] else 0.0
        if math.isfinite(ema20[i]) and math.isfinite(ema50[i]):
            signals["ema20_50_trend"][i] = 1.0 if ema20[i] > ema50[i] else 0.0
        if i >= 7 and closes[i - 7] > 0:
            momentum = closes[i] / closes[i - 7] - 1.0
            signals["momentum_7d_long_short"][i] = 1.0 if momentum > 0 else (-1.0 if momentum < 0 else 0.0)

    # Donchian entry uses only the previous 20 completed bars; exit uses the
    # previous 10 completed bars. The current bar is excluded from thresholds.
    holding = 0.0
    for i in range(n):
        if i >= 20 and all(math.isfinite(x) for x in highs[i - 20:i]):
            prior_high = max(highs[i - 20:i])
            prior_low10 = min(lows[i - 10:i]) if i >= 10 and all(math.isfinite(x) for x in lows[i - 10:i]) else math.nan
            if holding == 0.0 and closes[i] > prior_high:
                holding = 1.0
            elif holding == 1.0 and math.isfinite(prior_low10) and closes[i] < prior_low10:
                holding = 0.0
        signals["donchian20_10_breakout"][i] = holding

    holding = 0.0
    for i, value in enumerate(rsi14):
        if math.isfinite(value):
            if holding == 0.0 and value < 30.0:
                holding = 1.0
            elif holding == 1.0 and value > 50.0:
                holding = 0.0
        signals["rsi14_mean_reversion"][i] = holding
    return signals


def _metrics(rows, positions, cost_pct, capital_usd):
    opens = _float_series(rows, "open")
    start = max(200, 2)
    net_returns = []
    gross_returns = []
    turnover_costs = []
    active = []
    equity = float(capital_usd)
    peak = equity
    max_dd = 0.0
    for i in range(start, len(rows)):
        if not (math.isfinite(opens[i]) and math.isfinite(opens[i - 1]) and opens[i - 1] > 0):
            continue
        pos = positions[i]
        prev_pos = positions[i - 1]
        gross = pos * (opens[i] / opens[i - 1] - 1.0) * 100.0
        # A round-trip cost applies to a 0 -> 1 -> 0 cycle. Reversing from
        # +1 to -1 incurs one full round-trip cost at the reversal.
        cost = abs(pos - prev_pos) * (cost_pct / 2.0)
        net = gross - cost
        gross_returns.append(gross)
        net_returns.append(net)
        turnover_costs.append(cost)
        active.append(abs(pos) > 0)
        equity *= max(0.0, 1.0 + net / 100.0)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    n = len(net_returns)
    gains = sum(x for x in net_returns if x > 0)
    losses = abs(sum(x for x in net_returns if x < 0))
    daily_mean = mean(net_returns) if n else 0.0
    daily_sd = pstdev(net_returns) if n > 1 else 0.0
    net_profit = equity - capital_usd
    return {
        "bars": n,
        "net_profit_usd": round(net_profit, 4),
        "net_return_pct": round(net_profit / capital_usd * 100.0, 4) if capital_usd else 0.0,
        "gross_return_sum_pct": round(sum(gross_returns), 4),
        "estimated_cost_sum_pct": round(sum(turnover_costs), 4),
        "bar_profit_factor": round(gains / losses, 4) if losses else ("infinite" if gains else None),
        "annualized_sharpe_approx": round(daily_mean / daily_sd * math.sqrt(252), 4) if daily_sd else None,
        "max_drawdown_pct": round(max_dd, 4),
        "exposure_pct": round(sum(active) / n * 100.0, 2) if n else 0.0,
        "position_changes": sum(1 for i in range(1, len(positions)) if positions[i] != positions[i - 1]),
        "ending_equity_usd": round(equity, 4),
    }


def _evaluate(rows, signal, cost_pct, capital_usd, common_start, split_index):
    # A close-derived signal is executed at the next open. The open-to-open
    # return begins at that execution open, so shift the signal two rows to
    # align with the open-return series indexed by its ending bar.
    positions = [0.0] * len(signal)
    for i in range(2, len(signal)):
        positions[i] = signal[i - 2] if i - 2 >= common_start else 0.0
    # Same exact bars and capital convention for development and holdout.
    full = _metrics(rows[common_start:], positions[common_start:], cost_pct, capital_usd)
    # For slice metrics, rebase position series and OHLC rows, preserving only
    # positions whose signals were known before the first evaluated interval.
    dev_rows = rows[common_start:split_index]
    dev_pos = positions[common_start:split_index]
    oos_rows = rows[split_index:]
    oos_pos = positions[split_index:]
    return {
        "development": _metrics(dev_rows, dev_pos, cost_pct, capital_usd),
        "holdout_oos": _metrics(oos_rows, oos_pos, cost_pct, capital_usd),
        "full_sample": full,
    }


def tournament(bars, *, cost_round_trip_pct=0.35, capital_usd=500.0):
    rows = sorted(bars, key=lambda b: int(b.ts))
    if len(rows) < 700:
        return {
            "status": "insufficient_data",
            "bars": len(rows),
            "required_bars": 700,
            "research_only": True,
            "live_orders": False,
            "trade_ready": False,
        }
    timestamps = [int(b.ts) for b in rows]
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError("Timestamps must be strictly increasing with no duplicates.")
    for row in rows:
        o, h, l, c = (_float_series([row], key)[0] for key in ("open", "high", "low", "price"))
        if not all(math.isfinite(x) for x in (o, h, l, c)) or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("Input must contain valid OHLC bars; close-only data is rejected.")
    signals = build_signals(rows)
    common_start = 200
    split_index = common_start + int((len(rows) - common_start) * 0.70)
    results = {}
    for name in STRATEGY_NAMES:
        results[name] = _evaluate(rows, signals[name], cost_round_trip_pct, capital_usd, common_start, split_index)
    return {
        "status": "ok",
        "symbol": rows[-1].symbol,
        "interval": "1d",
        "bars": len(rows),
        "common_evaluation_start_ts": int(rows[common_start].ts),
        "holdout_start_ts": int(rows[split_index].ts),
        "development_fraction": 0.70,
        "cost_model": {
            "round_trip_cost_pct": float(cost_round_trip_pct),
            "position_change_cost_pct": float(cost_round_trip_pct / 2.0),
            "note": "Fixed cost stress, applied on position changes; no leverage. Actual fees/slippage can differ by venue and liquidity.",
        },
        "capital_usd": float(capital_usd),
        "strategy_results": results,
        "selection_policy": "No parameter search; fixed strategy definitions; last 30% chronological holdout is reported separately.",
        "research_only": True,
        "live_orders": False,
        "trade_ready": False,
        "trade_readiness_reason": "External strategy candidates require independent review, multiple untouched windows, cost sensitivity, and paper-shadow validation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cost-round-trip-pct", type=float, default=0.35)
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    bars = load_bars(args.input)
    result = tournament(bars, cost_round_trip_pct=args.cost_round_trip_pct, capital_usd=args.capital)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "symbol": result.get("symbol"),
        "status": result.get("status"),
        "bars": result.get("bars"),
        "cost_round_trip_pct": args.cost_round_trip_pct,
        "research_only": result.get("research_only"),
        "live_orders": result.get("live_orders"),
        "trade_ready": result.get("trade_ready"),
        "strategy_results": result.get("strategy_results"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
