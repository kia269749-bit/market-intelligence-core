"""Causal market-regime attribution for fixed strategy candidates.

This is descriptive OOS diagnostics, not an optimizer or production signal.
Regimes use only information available at the close that generated each signal.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import median, pstdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.storage import load_bars
from tools.external_strategy_tournament import STRATEGY_NAMES, build_signals, _float_series


def _rolling_mean(values, window):
    out = [math.nan] * len(values)
    for i in range(window - 1, len(values)):
        chunk = values[i - window + 1:i + 1]
        if all(math.isfinite(v) for v in chunk):
            out[i] = sum(chunk) / window
    return out


def _rolling_vol(values, window=20):
    out = [math.nan] * len(values)
    returns = [math.nan] * len(values)
    for i in range(1, len(values)):
        if math.isfinite(values[i]) and math.isfinite(values[i - 1]) and values[i - 1] > 0:
            returns[i] = values[i] / values[i - 1] - 1.0
    for i in range(window, len(values)):
        chunk = returns[i - window + 1:i + 1]
        if all(math.isfinite(v) for v in chunk):
            out[i] = pstdev(chunk)
    return out


def classify_regimes(rows, *, trend_window=200, fast_window=50, vol_window=20, vol_reference=100):
    """Causal labels: trend_up/trend_down/mixed crossed with high/low volatility."""
    closes = _float_series(rows, "price")
    slow = _rolling_mean(closes, trend_window)
    fast = _rolling_mean(closes, fast_window)
    vol = _rolling_vol(closes, vol_window)
    labels = ["unclassified"] * len(rows)
    for i in range(len(rows)):
        if not (math.isfinite(slow[i]) and math.isfinite(fast[i]) and math.isfinite(vol[i])):
            continue
        history = [v for v in vol[max(vol_window, i - vol_reference):i] if math.isfinite(v)]
        # Use only prior volatility observations, never the current/future distribution.
        if len(history) < min(30, vol_reference // 2):
            continue
        vol_state = "high_vol" if vol[i] > median(history) else "low_vol"
        if closes[i] > slow[i] and fast[i] > slow[i]:
            trend = "trend_up"
        elif closes[i] < slow[i] and fast[i] < slow[i]:
            trend = "trend_down"
        else:
            trend = "mixed"
        labels[i] = f"{trend}_{vol_state}"
    return labels


def analyze_regimes(bars, *, cost_round_trip_pct=0.35, capital_usd=500.0):
    rows = sorted(bars, key=lambda b: int(b.ts))
    if len(rows) < 700:
        return {"status": "insufficient_data", "bars": len(rows), "required_bars": 700,
                "research_only": True, "live_orders": False, "trade_ready": False}
    if any(b.ts <= a.ts for a, b in zip(rows, rows[1:])):
        raise ValueError("Timestamps must be strictly increasing.")
    for row in rows:
        o, h, l, c = (_float_series([row], key)[0] for key in ("open", "high", "low", "price"))
        if not all(math.isfinite(x) for x in (o, h, l, c)) or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("Valid OHLC bars are required.")
    regimes = classify_regimes(rows)
    signals = build_signals(rows)
    common_start = 200
    split_index = common_start + int((len(rows) - common_start) * 0.70)
    oos_start = split_index + 1
    opens = _float_series(rows, "open")
    result = {}
    for strategy, signal in signals.items():
        equity = float(capital_usd)
        previous_position = 0.0
        buckets = {}
        valid_bars = 0
        for i in range(oos_start, len(rows)):
            if not (math.isfinite(opens[i]) and math.isfinite(opens[i - 1]) and opens[i - 1] > 0):
                previous_position = 0.0
                continue
            # Signal generated at close[i-2], executed at open[i-1].
            signal_index = i - 2
            position = signal[signal_index] if signal_index >= common_start else 0.0
            label = regimes[signal_index] if signal_index >= 0 else "unclassified"
            gross_pct = position * (opens[i] / opens[i - 1] - 1.0) * 100.0
            cost_pct = abs(position - previous_position) * (cost_round_trip_pct / 2.0)
            net_pct = gross_pct - cost_pct
            prior_equity = equity
            equity *= max(0.0, 1.0 + net_pct / 100.0)
            pnl_usd = equity - prior_equity
            bucket = buckets.setdefault(label, {
                "bars": 0, "active_bars": 0, "net_profit_usd": 0.0,
                "gross_return_sum_pct": 0.0, "cost_sum_pct": 0.0,
                "positive_bar_pnl_usd": 0.0, "negative_bar_pnl_usd": 0.0,
                "position_changes": 0,
            })
            bucket["bars"] += 1
            bucket["active_bars"] += int(position != 0.0)
            bucket["net_profit_usd"] += pnl_usd
            bucket["gross_return_sum_pct"] += gross_pct
            bucket["cost_sum_pct"] += cost_pct
            if pnl_usd > 0:
                bucket["positive_bar_pnl_usd"] += pnl_usd
            elif pnl_usd < 0:
                bucket["negative_bar_pnl_usd"] += abs(pnl_usd)
            if position != previous_position:
                bucket["position_changes"] += 1
            previous_position = position
            valid_bars += 1
        for bucket in buckets.values():
            bucket["net_profit_usd"] = round(bucket["net_profit_usd"], 4)
            bucket["gross_return_sum_pct"] = round(bucket["gross_return_sum_pct"], 4)
            bucket["cost_sum_pct"] = round(bucket["cost_sum_pct"], 4)
            bucket["profit_factor_bar_pnl"] = round(
                bucket["positive_bar_pnl_usd"] / bucket["negative_bar_pnl_usd"], 4
            ) if bucket["negative_bar_pnl_usd"] else None
            bucket["exposure_pct"] = round(bucket["active_bars"] / bucket["bars"] * 100.0, 2) if bucket["bars"] else 0.0
            bucket.pop("positive_bar_pnl_usd", None)
            bucket.pop("negative_bar_pnl_usd", None)
        result[strategy] = {
            "oos_bars": valid_bars,
            "oos_ending_equity_usd": round(equity, 4),
            "oos_net_profit_usd": round(equity - capital_usd, 4),
            "regimes": dict(sorted(buckets.items())),
        }
    return {
        "status": "ok", "symbol": rows[-1].symbol, "interval": "1d", "bars": len(rows),
        "development_fraction": 0.70, "holdout_start_ts": int(rows[split_index].ts),
        "oos_start_index": oos_start, "cost_round_trip_pct": float(cost_round_trip_pct),
        "capital_usd": float(capital_usd), "regime_method": {
            "trend": "close versus SMA200 and SMA50; labels trend_up, trend_down, or mixed",
            "volatility": "20-bar realized volatility versus median of prior 100-bar volatility observations",
            "causal": True, "current_and_future_volatility_excluded_from_reference": True,
        },
        "strategy_results": result, "research_only": True, "live_orders": False,
        "trade_ready": False,
        "warning": "Regime buckets are descriptive and can be small; do not select a strategy from these same holdout buckets. Require new untouched windows and shadow validation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cost-round-trip-pct", type=float, default=0.35)
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    result = analyze_regimes(load_bars(args.input), cost_round_trip_pct=args.cost_round_trip_pct,
                             capital_usd=args.capital)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"symbol": result.get("symbol"), "status": result.get("status"),
                      "bars": result.get("bars"), "trade_ready": result.get("trade_ready"),
                      "strategy_results": result.get("strategy_results")}, sort_keys=True))


if __name__ == "__main__":
    main()
