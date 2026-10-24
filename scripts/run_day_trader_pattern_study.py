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
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mi_core.day_trader_pattern_eval import evaluate_day_trader_patterns

API_URL = "https://api.hyperliquid.xyz/info"
SYMBOLS = ("BTC", "ETH", "SOL")
INTERVAL = "1d"
FETCH_START = "2021-11-01T00:00:00Z"
FETCH_END = "2026-10-01T00:00:00Z"
SPLITS = (
    ("development", "2022-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    ("validation", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ("holdout", "2025-01-01T00:00:00Z", "2026-10-01T00:00:00Z"),
)


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
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            stamp = int(row["t"])
            opening = float(row["o"])
            high = float(row["h"])
            low = float(row["l"])
            close = float(row["c"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"malformed candle returned for {symbol}") from exc
        if stamp < _ms(FETCH_START) or stamp >= _ms(FETCH_END):
            continue
        if not all(value > 0 for value in (opening, high, low, close)):
            raise RuntimeError(f"non-positive OHLC candle returned for {symbol} at {stamp}")
        if high < max(opening, close, low) or low > min(opening, close, high):
            raise RuntimeError(f"inconsistent OHLC candle returned for {symbol} at {stamp}")
        by_time[stamp] = {
            "timestamp": stamp,
            "open": opening,
            "high": high,
            "low": low,
            "close": close,
        }
    candles = [by_time[key] for key in sorted(by_time)]
    if len(candles) < 500:
        raise RuntimeError(f"insufficient daily history for {symbol}: {len(candles)} candles")
    if len(candles) != len(by_time) or len({x["timestamp"] for x in candles}) != len(candles):
        raise RuntimeError(f"duplicate or inconsistent timestamps for {symbol}")
    return candles


def _split_with_warmup(candles: list[dict], start: str, end: str) -> tuple[list[dict], int]:
    start_ms, end_ms = _ms(start), _ms(end)
    first = next((i for i, bar in enumerate(candles) if bar["timestamp"] >= start_ms), None)
    if first is None:
        return [], 0
    stop = next((i for i, bar in enumerate(candles) if bar["timestamp"] >= end_ms), len(candles))
    if first < 20:
        raise RuntimeError(f"not enough pre-period warm-up bars for split starting {start}")
    # Exactly 20 prior daily bars are included so the first evaluated bar is
    # the split's first bar, not part of the warm-up.
    return candles[first - 20:stop], first - (first - 20)


def run_study() -> dict:
    result = {
        "protocol": {
            "data_source": "Hyperliquid public candleSnapshot",
            "symbols": list(SYMBOLS),
            "interval": INTERVAL,
            "fetch_start": FETCH_START,
            "fetch_end_exclusive": FETCH_END,
            "splits": [{"name": name, "start_inclusive": start, "end_exclusive": end} for name, start, end in SPLITS],
            "horizon_bars": 5,
            "cost_multipliers": [1.0, 1.5, 2.0],
            "strategy_parameters_frozen": True,
            "research_only": True,
            "live_orders": False,
        },
        "assets": {},
    }
    for symbol in SYMBOLS:
        candles = fetch_daily(symbol)
        asset_result = {"candles": len(candles), "first_timestamp": candles[0]["timestamp"], "last_timestamp": candles[-1]["timestamp"], "splits": {}}
        for name, start, end in SPLITS:
            segment, _ = _split_with_warmup(candles, start, end)
            if len(segment) < 30:
                raise RuntimeError(f"insufficient data for {symbol} {name} split")
            metrics = evaluate_day_trader_patterns(segment, horizon_bars=5)
            metrics["period"] = {"start_inclusive": start, "end_exclusive": end}
            asset_result["splits"][name] = metrics
        result["assets"][symbol] = asset_result
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
