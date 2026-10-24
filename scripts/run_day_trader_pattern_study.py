#!/usr/bin/env python3
"""Fetch public Hyperliquid daily candles and run a preregistered pattern study.

This is a read-only research utility. It never authenticates, reads private
account data, or submits orders. The fixed periods and cost stress are locked
here to reduce post-hoc selection.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from math import isfinite
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mi_core.day_trader_pattern_eval import evaluate_day_trader_patterns
from mi_core.pattern_statistics import bootstrap_edge_test, bootstrap_mean_ci, holm_adjust

API_URL = "https://api.hyperliquid.xyz/info"
SYMBOLS = ("BTC", "ETH", "SOL")
INTERVAL = "1d"
DAY_MS = 86_400_000
FETCH_START = "2021-11-01T00:00:00Z"
FETCH_END = "2026-10-01T00:00:00Z"
SPLITS = (
    ("development", "2022-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    ("validation", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ("holdout", "2025-01-01T00:00:00Z", "2026-10-01T00:00:00Z"),
)
# Frozen-pattern calendar subperiods expose year-to-year instability without
# tuning parameters on these slices. 2026 is partial through FETCH_END.
FROZEN_SUBPERIODS = (
    ("year_2022", "2022-01-01T00:00:00Z", "2023-01-01T00:00:00Z"),
    ("year_2023", "2023-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    ("year_2024", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ("year_2025", "2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    ("year_2026_partial", "2026-01-01T00:00:00Z", "2026-10-01T00:00:00Z"),
)
ALL_SPLITS = SPLITS + FROZEN_SUBPERIODS


def _ms(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1000)


def _post(payload: dict) -> object:
    data = json.dumps(payload).encode("utf-8")
    request = Request(API_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "market-intelligence-core-research/1.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Hyperliquid public candle request failed after retries: {last_error}")


def fetch_daily(symbol: str) -> list[dict]:
    raw = _post({
        "type": "candleSnapshot",
        "req": {
            "coin": symbol,
            "interval": INTERVAL,
            "startTime": _ms(FETCH_START),
            "endTime": _ms(FETCH_END),
        },
    })
    if not isinstance(raw, list):
        raise RuntimeError(f"unexpected candle response for {symbol}: expected list")
    by_time = {}
    duplicate_timestamps = set()
    for row in raw:
        if not isinstance(row, dict):
            raise RuntimeError(f"malformed candle row returned for {symbol}")
        try:
            stamp = int(row["t"])
            opening, high, low, close = (float(row[key]) for key in ("o", "h", "l", "c"))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"malformed candle returned for {symbol}") from exc
        if stamp < _ms(FETCH_START) or stamp >= _ms(FETCH_END):
            continue
        if not all(isfinite(value) and value > 0 for value in (opening, high, low, close)):
            raise RuntimeError(f"non-finite or non-positive OHLC candle returned for {symbol} at {stamp}")
        if high < max(opening, close, low) or low > min(opening, close, high):
            raise RuntimeError(f"inconsistent OHLC candle returned for {symbol} at {stamp}")
        if stamp in by_time:
            duplicate_timestamps.add(stamp)
        by_time[stamp] = {
            "timestamp": stamp,
            "open": opening,
            "high": high,
            "low": low,
            "close": close,
        }
    if duplicate_timestamps:
        raise RuntimeError(f"duplicate timestamps for {symbol}: {sorted(duplicate_timestamps)[:3]}")
    candles = [by_time[key] for key in sorted(by_time)]
    if len(candles) < 500:
        raise RuntimeError(f"insufficient daily history for {symbol}: {len(candles)} candles")
    for previous, current in zip(candles, candles[1:]):
        if current["timestamp"] - previous["timestamp"] != DAY_MS:
            raise RuntimeError(
                f"missing or irregular daily candle interval for {symbol}: "
                f"{previous['timestamp']} -> {current['timestamp']}"
            )
    return candles


def _split_with_warmup(candles: list[dict], start: str, end: str) -> list[dict]:
    start_ms, end_ms = _ms(start), _ms(end)
    first = next((i for i, bar in enumerate(candles) if bar["timestamp"] >= start_ms), None)
    if first is None:
        return []
    stop = next((i for i, bar in enumerate(candles) if bar["timestamp"] >= end_ms), len(candles))
    if first < 20:
        raise RuntimeError(f"not enough pre-period warm-up bars for split starting {start}")
    # Exactly 20 prior daily bars ensure the evaluator's first signal bar is
    # the first bar in the split, not part of the warm-up.
    return candles[first - 20:stop]


def run_study() -> dict:
    result = {
        "protocol": {
            "data_source": "Hyperliquid public candleSnapshot",
            "symbols": list(SYMBOLS),
            "interval": INTERVAL,
            "fetch_start": FETCH_START,
            "fetch_end_exclusive": FETCH_END,
            "splits": [{"name": name, "start_inclusive": start, "end_exclusive": end} for name, start, end in SPLITS],
            "frozen_parameter_subperiods": [
                {"name": name, "start_inclusive": start, "end_exclusive": end}
                for name, start, end in FROZEN_SUBPERIODS
            ],
            "horizon_bars": 5,
            "cost_multipliers": [1.0, 1.5, 2.0],
            "strategy_parameters_frozen": True,
            "research_only": True,
            "live_orders": False,
        },
        "assets": {},
        "statistical_validation": {},
    }
    tests_by_family = {}
    for symbol in SYMBOLS:
        candles = fetch_daily(symbol)
        asset_result = {
            "candles": len(candles),
            "first_timestamp": candles[0]["timestamp"],
            "last_timestamp": candles[-1]["timestamp"],
            "splits": {},
        }
        for name, start, end in ALL_SPLITS:
            segment = _split_with_warmup(candles, start, end)
            if len(segment) < 30:
                raise RuntimeError(f"insufficient data for {symbol} {name} split")
            metrics = evaluate_day_trader_patterns(segment, horizon_bars=5)
            metrics["period"] = {"start_inclusive": start, "end_exclusive": end}
            asset_result["splits"][name] = metrics
            for pattern_name, pattern_result in metrics.get("strategies", {}).items():
                for multiplier, stress in pattern_result.get("stress", {}).items():
                    family_key = (name, multiplier)
                    family = tests_by_family.setdefault(family_key, [])
                    seed = 20261024 + sum(ord(ch) for ch in f"{symbol}:{name}:{pattern_name}:{multiplier}")
                    returns = stress.get("net_returns_pct", [])
                    baseline_returns = stress.get("baseline_net_returns_pct", [])
                    family.append({
                        "asset": symbol,
                        "pattern": pattern_name,
                        "cost_multiplier": multiplier,
                        "net_return_ci": bootstrap_mean_ci(returns, reps=2000, block_size=3, seed=seed),
                        "edge_test": bootstrap_edge_test(
                            returns, baseline_returns, reps=2000, block_size=3, seed=seed + 1
                        ),
                    })
        result["assets"][symbol] = asset_result
    for (split_name, multiplier), family in sorted(tests_by_family.items()):
        adjusted = holm_adjust([
            row["edge_test"].get("p_value_one_sided") for row in family
        ])
        for row, adjusted_p in zip(family, adjusted):
            row["holm_adjusted_p_value"] = adjusted_p
        result["statistical_validation"].setdefault(split_name, {})[multiplier] = {
            "family_size_including_insufficient_samples": len(family),
            "multiple_testing_correction": "Holm-Bonferroni",
            "tests": family,
            "interpretation": (
                "Exploratory diagnostics only. LOW_SAMPLE and INSUFFICIENT_DATA are not "
                "positive evidence; intervals and p-values do not model funding or live fills."
            ),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/day_trader_pattern_study.json")
    args = parser.parse_args()
    report = run_study()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"REPORT_PATH={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
