"""Read-only Hyperliquid perpetual candles and historical funding data.

The public info API provides candles and discrete funding events. This module
does not pretend historical open interest is available: OI remains null.
Funding is aligned strictly backward to candle close, with event timestamps
preserved for holding-period funding-cost calculations.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

INFO_URL = "https://api.hyperliquid.xyz/info"
CHUNK_MS = 14 * 24 * 60 * 60 * 1000
KLINE_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "8h": 28_800_000, "12h": 43_200_000,
    "1d": 86_400_000, "3d": 259_200_000, "1w": 604_800_000,
}


@dataclass(frozen=True)
class PerpCandle:
    coin: str
    timestamp_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


@dataclass(frozen=True)
class FundingEvent:
    coin: str
    timestamp_ms: int
    rate: float


def _post_info(payload: dict[str, Any], timeout: float = 20.0) -> Any:
    request = Request(
        INFO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "market-intelligence-core-research/1"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Hyperliquid info endpoint returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Hyperliquid public data request failed: {type(exc).__name__}") from exc


def _finite(value: Any, field: str, *, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError(f"invalid {field}")
    return number


def fetch_candles(
    coin: str, interval: str, start_ms: int, end_ms: int, *,
    post_json: Callable[[dict[str, Any]], Any] = _post_info,
) -> list[PerpCandle]:
    """Fetch complete candles in bounded, interval-aligned chunks."""
    if not coin or interval not in KLINE_INTERVAL_MS:
        raise ValueError("coin and supported Hyperliquid candle interval are required")
    if int(start_ms) < 0 or int(end_ms) <= int(start_ms):
        raise ValueError("end_ms must be greater than non-negative start_ms")
    interval_ms = KLINE_INTERVAL_MS[interval]
    start_bound = ((int(start_ms) + interval_ms - 1) // interval_ms) * interval_ms
    end_bound = (int(end_ms) // interval_ms) * interval_ms - 1
    if end_bound < start_bound:
        return []
    window_ms = min((CHUNK_MS // interval_ms) * interval_ms, interval_ms * 4000)
    window_ms = max(interval_ms, window_ms)
    candles: list[PerpCandle] = []
    cursor = start_bound
    while cursor <= end_bound:
        chunk_end = min(cursor + window_ms - 1, end_bound)
        raw = post_json({
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": interval, "startTime": cursor, "endTime": chunk_end},
        })
        if not isinstance(raw, list):
            raise ValueError("unexpected candle response: expected a list")
        for row in raw:
            if not isinstance(row, dict):
                continue
            candle = PerpCandle(
                coin=coin,
                timestamp_ms=int(row.get("t")),
                close_time_ms=int(row.get("T", row.get("t"))),
                open=_finite(row.get("o"), "open", minimum=0.0),
                high=_finite(row.get("h"), "high", minimum=0.0),
                low=_finite(row.get("l"), "low", minimum=0.0),
                close=_finite(row.get("c"), "close", minimum=0.0),
                volume=_finite(row.get("v", 0), "volume", minimum=0.0),
                trades=int(row.get("n", 0) or 0),
            )
            if min(candle.open, candle.high, candle.low, candle.close) <= 0:
                raise ValueError("candle prices must be positive")
            if candle.high < max(candle.open, candle.close, candle.low) or candle.low > min(candle.open, candle.close, candle.high):
                raise ValueError("inconsistent candle OHLC values")
            if start_bound <= candle.timestamp_ms <= chunk_end and candle.close_time_ms <= chunk_end:
                candles.append(candle)
        if chunk_end >= end_bound:
            break
        cursor = chunk_end + 1
    by_time = {item.timestamp_ms: item for item in candles}
    return [by_time[k] for k in sorted(by_time)]


def fetch_funding_history(
    coin: str, start_ms: int, end_ms: int, *,
    post_json: Callable[[dict[str, Any]], Any] = _post_info,
) -> list[FundingEvent]:
    """Fetch realized discrete funding events in bounded 14-day windows."""
    if not coin or int(start_ms) < 0 or int(end_ms) <= int(start_ms):
        raise ValueError("coin and valid funding time range are required")
    events: list[FundingEvent] = []
    cursor = int(start_ms)
    while cursor <= int(end_ms):
        chunk_end = min(cursor + CHUNK_MS, int(end_ms))
        raw = post_json({
            "type": "fundingHistory", "coin": coin,
            "startTime": cursor, "endTime": chunk_end,
        })
        if not isinstance(raw, list):
            raise ValueError("unexpected funding response: expected a list")
        for row in raw:
            if not isinstance(row, dict):
                continue
            rate = _finite(row.get("fundingRate"), "fundingRate")
            if not -1.0 <= rate <= 1.0:
                raise ValueError("funding rate outside defensive bounds")
            timestamp_ms = int(row["time"])
            if int(start_ms) <= timestamp_ms <= int(end_ms):
                events.append(FundingEvent(coin, timestamp_ms, rate))
        if chunk_end >= int(end_ms):
            break
        cursor = chunk_end + 1
    by_time = {item.timestamp_ms: item for item in events}
    return [by_time[k] for k in sorted(by_time)]


def funding_rates_at_candle_close(candles: list[PerpCandle], events: list[FundingEvent]) -> list[float | None]:
    """Model-only alignment: latest fetched event with timestamp <= candle close."""
    ordered = sorted(events, key=lambda item: item.timestamp_ms)
    j = 0
    latest: FundingEvent | None = None
    out: list[float | None] = []
    for candle in sorted(candles, key=lambda item: item.timestamp_ms):
        while j < len(ordered) and ordered[j].timestamp_ms <= candle.close_time_ms:
            latest = ordered[j]
            j += 1
        out.append(latest.rate if latest is not None else None)
    return out


def join_funding_feature(candles: list[PerpCandle], events: list[FundingEvent]) -> list[float | None]:
    """Carry the last known rate for display only; not a cashflow calculation."""
    ordered = sorted(events, key=lambda item: item.timestamp_ms)
    j = 0
    latest: float | None = None
    out = []
    for candle in sorted(candles, key=lambda item: item.timestamp_ms):
        while j < len(ordered) and ordered[j].timestamp_ms < candle.close_time_ms:
            latest = ordered[j].rate
            j += 1
        out.append(latest)
    return out


def project60_rows(
    coin: str, asset_key: str, candles: list[PerpCandle], events: list[FundingEvent], *,
    funding_max_age_ms: int = 2 * 60 * 60 * 1000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered_events = sorted(events, key=lambda item: item.timestamp_ms)
    event_index = 0
    latest: FundingEvent | None = None
    rows = []
    funding_present = funding_fresh = 0
    for candle in sorted(candles, key=lambda item: item.timestamp_ms):
        while event_index < len(ordered_events) and ordered_events[event_index].timestamp_ms < candle.close_time_ms:
            latest = ordered_events[event_index]
            event_index += 1
        age = candle.close_time_ms - latest.timestamp_ms if latest else None
        fresh = latest is not None and age is not None and 0 <= age <= funding_max_age_ms
        funding_present += latest is not None
        funding_fresh += fresh
        rows.append({
            "timestamp": int(candle.close_time_ms),
            "coins": {
                asset_key: {
                    "price": candle.close,
                    "open": candle.open, "high": candle.high, "low": candle.low,
                    "volume": candle.volume,
                    "open_interest": None,
                    "funding": latest.rate if latest else None,
                    "trades": {"buy_usd": None, "sell_usd": None},
                    "orderbook": {"bid_usd": None, "ask_usd": None},
                    "derivatives": {
                        "oi_timestamp_ms": None, "oi_age_ms": None, "oi_max_age_ms": None,
                        "funding_timestamp_ms": int(latest.timestamp_ms) if latest else None,
                        "funding_age_ms": age,
                        "funding_max_age_ms": int(funding_max_age_ms),
                    },
                }
            },
        })
    n = len(rows)
    coverage = {
        "venue": "Hyperliquid", "instrument": "perpetual",
        "coin": coin, "asset_key": asset_key, "bars": n,
        "funding_events_fetched": len(events),
        "funding_present": funding_present,
        "funding_coverage_pct": round(100.0 * funding_present / n, 4) if n else 0.0,
        "funding_fresh_present": funding_fresh,
        "funding_fresh_coverage_pct": round(100.0 * funding_fresh / n, 4) if n else 0.0,
        "oi_present": 0, "oi_coverage_pct": 0.0,
        "oi_status": "no_historical_oi_feed_in_this_adapter",
        "alignment": "funding_events_strictly_before_candle_close_no_lookahead",
        "funding_is_execution_carry_not_predictive_feature": True,
        "features_enabled": False,
    }
    return rows, coverage


def download_project60(
    coin: str, interval: str = "1h", bars: int = 8000,
    out: str = "data/real/hyperliquid_project60.jsonl", *,
    asset_key: str | None = None, start_ms: int | None = None, end_ms: int | None = None,
    post_json: Callable[[dict[str, Any]], Any] = _post_info, overwrite: bool = False,
) -> tuple[Path, dict[str, Any]]:
    if interval not in KLINE_INTERVAL_MS or not 1 <= int(bars) <= 10_000:
        raise ValueError("supported interval and bars between 1 and 10000 are required")
    target = Path(out)
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing data file: {target}")
    interval_ms = KLINE_INTERVAL_MS[interval]
    end_bound = int(end_ms) if end_ms is not None else int(time.time() * 1000)
    if start_ms is not None:
        start_bound = int(start_ms)
    else:
        aligned_end = (end_bound // interval_ms) * interval_ms - 1
        start_bound = max(0, aligned_end - interval_ms * int(bars) + 1)
    candles = fetch_candles(coin, interval, start_bound, end_bound, post_json=post_json)
    if not candles:
        raise RuntimeError("Hyperliquid returned no perpetual candles")
    funding_start = max(0, start_bound - 9 * 60 * 60 * 1000)
    events = fetch_funding_history(coin, funding_start, end_bound, post_json=post_json)
    rows, coverage = project60_rows(coin, asset_key or coin, candles, events)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    coverage.update({
        "requested_bars": int(bars),
        "requested_start_ms": start_bound,
        "requested_end_ms": end_bound,
        "first_candle_ms": candles[0].timestamp_ms,
        "last_candle_close_ms": candles[-1].close_time_ms,
        "output": str(target),
    })
    return target, coverage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download Hyperliquid perpetual candles and funding for Project60")
    parser.add_argument("--coin", required=True, help="Hyperliquid coin, e.g. BTC")
    parser.add_argument("--asset-key", default="", help="Project60 key, e.g. BTCUSDT")
    parser.add_argument("--interval", choices=tuple(KLINE_INTERVAL_MS), default="1h")
    parser.add_argument("--bars", type=int, default=8000)
    parser.add_argument("--start-ms", type=int, default=None)
    parser.add_argument("--end-ms", type=int, default=None)
    parser.add_argument("--out", default="data/real/hyperliquid_project60.jsonl")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    path, coverage = download_project60(
        args.coin, args.interval, args.bars, args.out,
        asset_key=args.asset_key or None, start_ms=args.start_ms,
        end_ms=args.end_ms, overwrite=args.overwrite,
    )
    print(json.dumps({"path": str(path), "coverage": coverage}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
