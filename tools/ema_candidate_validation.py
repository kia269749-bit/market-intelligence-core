"""Independent, fixed-rule EMA20/50 candidate validation.

Uses completed daily candles, next-open execution, open-to-open returns, reset
capital for each calendar-year window, explicit round-trip cost sensitivity,
and buy-and-hold/SMA200/Donchian/RSI comparators. This is research only.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.storage import load_bars


STRATEGIES = ("ema20_50", "ema20_50_sma200_confirmed", "ema20_50_long_short", "ema20_50_sma200_long_short", "sma200", "donchian20_10", "rsi14", "buy_and_hold")
DEFAULT_COSTS = (0.24,)


def _series(rows, key):
    values = []
    for row in rows:
        value = getattr(row, key, None)
        if key == "close" and value is None:
            value = getattr(row, "price", None)
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = math.nan
        values.append(value if math.isfinite(value) and value > 0 else math.nan)
    return values


def _ema(values, window):
    result = [math.nan] * len(values)
    alpha = 2.0 / (window + 1.0)
    if len(values) < window:
        return result
    for i in range(window - 1, len(values)):
        seed = values[i - window + 1:i + 1]
        if i == window - 1:
            if all(math.isfinite(x) for x in seed):
                result[i] = sum(seed) / window
        elif math.isfinite(values[i]) and math.isfinite(result[i - 1]):
            result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]
    return result


def _sma(values, window):
    result = [math.nan] * len(values)
    for i in range(window - 1, len(values)):
        chunk = values[i - window + 1:i + 1]
        if all(math.isfinite(x) for x in chunk):
            result[i] = sum(chunk) / window
    return result


def _rsi(values, window=14):
    result = [math.nan] * len(values)
    if len(values) <= window or not all(math.isfinite(x) for x in values):
        return result
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(x, 0.0) for x in changes]
    losses = [max(-x, 0.0) for x in changes]
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window

    def value(gain, loss):
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    result[window] = value(avg_gain, avg_loss)
    for i in range(window + 1, len(values)):
        avg_gain = ((window - 1) * avg_gain + gains[i - 1]) / window
        avg_loss = ((window - 1) * avg_loss + losses[i - 1]) / window
        result[i] = value(avg_gain, avg_loss)
    return result


def validate_bars(rows, expected_symbol=None):
    if len(rows) < 700:
        raise ValueError(f"at least 700 daily bars required; got {len(rows)}")
    stamps = [int(row.ts) for row in rows]
    if any(b <= a for a, b in zip(stamps, stamps[1:])):
        raise ValueError("timestamps must be strictly increasing and unique")
    symbols = {str(getattr(row, "symbol", "")) for row in rows}
    if len(symbols) != 1 or (expected_symbol and symbols != {expected_symbol}):
        raise ValueError(f"symbol mismatch: expected {expected_symbol!r}, found {sorted(symbols)}")
    opens, highs, lows, closes = (_series(rows, key) for key in ("open", "high", "low", "price"))
    for i, (o, h, low, c) in enumerate(zip(opens, highs, lows, closes)):
        if not all(math.isfinite(x) for x in (o, h, low, c)):
            raise ValueError(f"invalid OHLC value at row {i}")
        if h < max(o, c, low) or low > min(o, c, h):
            raise ValueError(f"inconsistent OHLC values at row {i}")
    return next(iter(symbols)), stamps


def build_signals(rows):
    """Build close-time target positions; execution is delayed by the evaluator."""
    closes = _series(rows, "price")
    highs = _series(rows, "high")
    lows = _series(rows, "low")
    n = len(rows)
    if n < 210:
        raise ValueError("at least 210 bars required for indicator warm-up")
    e20, e50 = _ema(closes, 20), _ema(closes, 50)
    s200, rsi = _sma(closes, 200), _rsi(closes)
    signals = {name: [0.0] * n for name in STRATEGIES}
    for i in range(n):
        signals["buy_and_hold"][i] = 1.0
        if math.isfinite(e20[i]) and math.isfinite(e50[i]):
            signals["ema20_50"][i] = 1.0 if e20[i] > e50[i] else 0.0
            signals["ema20_50_long_short"][i] = 1.0 if e20[i] > e50[i] else -1.0 if e20[i] < e50[i] else 0.0
        if math.isfinite(e20[i]) and math.isfinite(e50[i]) and math.isfinite(s200[i]):
            signals["ema20_50_sma200_confirmed"][i] = 1.0 if e20[i] > e50[i] and closes[i] > s200[i] else 0.0
            if e20[i] > e50[i] and closes[i] > s200[i]:
                signals["ema20_50_sma200_long_short"][i] = 1.0
            elif e20[i] < e50[i] and closes[i] < s200[i]:
                signals["ema20_50_sma200_long_short"][i] = -1.0
        if math.isfinite(s200[i]):
            signals["sma200"][i] = 1.0 if closes[i] > s200[i] else 0.0

    holding = 0.0
    for i in range(n):
        if i >= 20 and all(math.isfinite(x) for x in highs[i - 20:i]):
            prior_high = max(highs[i - 20:i])
            prior_low = min(lows[i - 10:i]) if i >= 10 and all(
                math.isfinite(x) for x in lows[i - 10:i]
            ) else math.nan
            if holding == 0.0 and closes[i] > prior_high:
                holding = 1.0
            elif holding == 1.0 and math.isfinite(prior_low) and closes[i] < prior_low:
                holding = 0.0
        signals["donchian20_10"][i] = holding

    holding = 0.0
    for i, value in enumerate(rsi):
        if math.isfinite(value):
            if holding == 0.0 and value < 30.0:
                holding = 1.0
            elif holding == 1.0 and value > 50.0:
                holding = 0.0
        signals["rsi14"][i] = holding
    return signals


def score_window(rows, signal, start, end, round_trip_cost_pct, capital_usd=500.0):
    """Score a fresh account for [start, end); indicators may use prior history."""
    opens = _series(rows, "open")
    equity = peak = float(capital_usd)
    max_dd = 0.0
    changes = exposure = 0
    daily_net = []
    daily_gross = []
    first_i = max(start + 1, 1)
    for i in range(first_i, min(end, len(rows))):
        if not (math.isfinite(opens[i - 1]) and math.isfinite(opens[i])):
            continue
        # Signal from close[i-2] is available before open[i-1], which starts
        # this open-to-open return. No current/future candle is consulted.
        pos = signal[i - 2] if i >= 2 else 0.0
        prev = 0.0 if i == first_i else (signal[i - 3] if i >= 3 else 0.0)
        gross = pos * (opens[i] / opens[i - 1] - 1.0) * 100.0
        cost = abs(pos - prev) * (round_trip_cost_pct / 2.0)
        net = gross - cost
        if pos != prev:
            changes += 1
        exposure += int(abs(pos) > 0)
        daily_gross.append(gross)
        daily_net.append(net)
        equity *= max(0.0, 1.0 + net / 100.0)
        peak = max(peak, equity)
        if peak:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    gains = sum(x for x in daily_net if x > 0)
    losses = abs(sum(x for x in daily_net if x < 0))
    sd = pstdev(daily_net) if len(daily_net) > 1 else 0.0
    return {
        "bars": len(daily_net),
        "net_profit_usd": round(equity - capital_usd, 4),
        "net_return_pct": round((equity / capital_usd - 1.0) * 100.0, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "profit_factor": round(gains / losses, 4) if losses else ("infinite" if gains else None),
        "mean_daily_net_pct": round(mean(daily_net), 6) if daily_net else 0.0,
        "daily_sharpe_approx": round(mean(daily_net) / sd * math.sqrt(252), 4) if sd else None,
        "position_changes": changes,
        "exposure_pct": round(exposure / len(daily_net) * 100.0, 2) if daily_net else 0.0,
    }


def _daily_net_returns(rows, signal, start, end, round_trip_cost_pct):
    """Paired daily net returns for a reset account over a date window."""
    opens = _series(rows, "open")
    returns = []
    first_i = max(start + 1, 1)
    for i in range(first_i, min(end, len(rows))):
        pos = signal[i - 2] if i >= 2 else 0.0
        prev = 0.0 if i == first_i else (signal[i - 3] if i >= 3 else 0.0)
        gross = pos * (opens[i] / opens[i - 1] - 1.0) * 100.0
        returns.append(gross - abs(pos - prev) * (round_trip_cost_pct / 2.0))
    return returns


def _moving_block_mean_ci(differences, *, block_length=20, replicates=1000, seed=0):
    """Exploratory paired moving-block bootstrap CI for mean daily excess return."""
    n = len(differences)
    if n < max(60, block_length * 3):
        return None
    rng = random.Random(seed)
    means = []
    max_start = n - block_length
    for _ in range(replicates):
        sample = []
        while len(sample) < n:
            start = rng.randrange(max_start + 1)
            sample.extend(differences[start:start + block_length])
        means.append(sum(sample[:n]) / n)
    means.sort()
    return {
        "ci95_low_mean_daily_excess_pct": round(means[int(0.025 * (replicates - 1))], 7),
        "ci95_high_mean_daily_excess_pct": round(means[int(0.975 * (replicates - 1))], 7),
        "bootstrap_replicates": replicates,
        "block_length_days": block_length,
    }


def validate_candidate(bars, expected_symbol=None, costs=DEFAULT_COSTS, capital_usd=500.0):
    if tuple(float(c) for c in costs) != (0.24,):
        raise ValueError("project cost is fixed at 0.24% round trip")
    symbol, stamps = validate_bars(bars, expected_symbol)
    signals = build_signals(bars)
    years = {}
    for i, stamp in enumerate(stamps):
        year = datetime.fromtimestamp(stamp / 1000.0, timezone.utc).year
        years.setdefault(year, []).append(i)

    windows = []
    # Skip partial initial years; retain the current partial year but label it.
    for year, indices in sorted(years.items()):
        start, end = indices[0], indices[-1] + 1
        if year < 2021 or end - start < 180:
            continue
        year_start = datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
        next_year_start = datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
        full_year = stamps[start] <= year_start + 3 * 86400000 and stamps[end - 1] >= next_year_start - 5 * 86400000
        for cost in costs:
            strategies = {
                name: score_window(bars, signals[name], start, end, float(cost), capital_usd)
                for name in STRATEGIES
            }
            windows.append({
                "year": year,
                "window_type": "full_calendar_year" if full_year else "partial_calendar_year",
                "bars": end - start,
                "round_trip_cost_pct": float(cost),
                "strategies": strategies,
            })

    aggregate = {}
    for cost in costs:
        selected = [w for w in windows if w["round_trip_cost_pct"] == float(cost) and w["window_type"] == "full_calendar_year"]
        aggregate[str(cost)] = {}
        for name in STRATEGIES:
            values = [w["strategies"][name]["net_profit_usd"] for w in selected]
            aggregate[str(cost)][name] = {
                "windows": len(values),
                "positive_windows": sum(x > 0 for x in values),
                "negative_windows": sum(x < 0 for x in values),
                "flat_windows": sum(x == 0 for x in values),
                "total_net_profit_usd": round(sum(values), 4) if values else None,
                "mean_window_net_profit_usd": round(mean(values), 4) if values else None,
                "median_window_net_profit_usd": round(median(values), 4) if values else None,
                "windows_beating_buy_and_hold": sum(
                    w["strategies"][name]["net_profit_usd"] > w["strategies"]["buy_and_hold"]["net_profit_usd"]
                    for w in selected
                ) if name != "buy_and_hold" else None,
                "mean_max_drawdown_pct": round(mean(
                    w["strategies"][name]["max_drawdown_pct"] for w in selected
                ), 4) if selected else None,
            }
    bootstrap_by_cost = {}
    # A single fixed 2021-2025 evaluation window per asset. This is descriptive
    # and exploratory because the candidate was selected after prior research.
    if 2021 in years and 2025 in years:
        period_start, period_end = years[2021][0], years[2025][-1] + 1
        for cost in costs:
            per_strategy = {}
            benchmark = _daily_net_returns(
                bars, signals["buy_and_hold"], period_start, period_end, float(cost)
            )
            for name in ("ema20_50", "ema20_50_sma200_confirmed"):
                candidate = _daily_net_returns(
                    bars, signals[name], period_start, period_end, float(cost)
                )
                paired = [a - b for a, b in zip(candidate, benchmark)]
                seed = sum((i + 1) * ord(ch) for i, ch in enumerate(f"{symbol}|{cost}|{name}"))
                ci = _moving_block_mean_ci(paired, block_length=20, replicates=1000, seed=seed)
                per_strategy[name] = {
                    "days": len(paired),
                    "mean_daily_excess_pct": round(mean(paired), 7) if paired else None,
                    **(ci or {}),
                    "ci_lower_above_zero": bool(ci and ci["ci95_low_mean_daily_excess_pct"] > 0),
                }
            bootstrap_by_cost[str(float(cost))] = per_strategy

    return {
        "status": "ok",
        "symbol": symbol,
        "interval": "1d",
        "bars": len(bars),
        "first_timestamp_ms": stamps[0],
        "last_timestamp_ms": stamps[-1],
        "source_context": "public Binance spot OHLCV; not Hyperliquid perpetual execution data",
        "method": {
            "strategy_parameters_fixed": True,
            "parameter_search": False,
            "execution": "signal from completed close, delayed to next open; open-to-open returns",
            "windowing": "fresh $500 account for each calendar-year slice; prior bars used only for indicator warm-up",
            "fixed_round_trip_cost_pct": 0.24,
            "comparators": list(STRATEGIES),
            "limitations": [
                "primary aggregate includes full calendar years only; partial final year remains visible in raw windows but is excluded from aggregate",
            "calendar-year slices are not statistically independent",
            "block-bootstrap intervals are exploratory after candidate selection and do not establish a durable edge",
                "no funding, borrow, liquidation, order-book impact, or actual LBank fills",
                "positive historical return is not proof of future edge",
                "partial final-year window is not directly comparable with full years",
            ],
        },
        "windows": windows,
        "aggregate_by_cost": aggregate,
        "exploratory_block_bootstrap_vs_buy_and_hold": {
            "period": "full calendar years 2021-2025",
            "interpretation": "paired 20-day moving-block bootstrap of mean daily net-return difference; descriptive only, not a confirmatory significance test",
            "by_cost": bootstrap_by_cost,
        },
        "research_only": True,
        "live_orders": False,
        "trade_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--costs", default="0.24", help="locked project baseline: 0.24 percent round trip")
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    costs = tuple(float(x.strip()) for x in args.costs.split(",") if x.strip())
    if costs != (0.24,):
        raise SystemExit("--costs is locked to the project baseline: --costs 0.24")
    bars = load_bars(args.input)
    report = validate_candidate(bars, expected_symbol=args.symbol, costs=costs, capital_usd=args.capital)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "symbol": report["symbol"], "bars": report["bars"],
        "windows": len(report["windows"]), "aggregate_by_cost": report["aggregate_by_cost"],
        "research_only": True, "live_orders": False, "trade_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
