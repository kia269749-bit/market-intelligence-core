"""Public Binance USD-M futures candles, funding, and open-interest history.

This collector is additive: the existing Binance Spot collector is untouched.
All derivative values are aligned strictly backward to candle close times.
Missing observations remain None and are accompanied by source timestamps and
coverage metadata. No credentials, account endpoints, or order endpoints are used.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
OPEN_INTEREST_URL = "https://fapi.binance.com/futures/data/openInterestHist"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"

PERIOD_MS = {
    "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "6h": 21_600_000, "12h": 43_200_000, "1d": 86_400_000,
}


@dataclass(frozen=True)
class FuturesCandle:
    symbol: str
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    taker_buy_quote_volume: float
    trades: int


@dataclass(frozen=True)
class OpenInterestSnapshot:
    symbol: str
    timestamp_ms: int
    open_interest: float
    open_interest_value: float | None = None


@dataclass(frozen=True)
class FundingEvent:
    symbol: str
    timestamp_ms: int
    rate: float


def _get_json(url: str, params: dict[str, Any], timeout: float = 20.0) -> Any:
    request = Request(
        url + "?" + urlencode(params),
        headers={"User-Agent": "market-intelligence-core-research/1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Binance futures endpoint returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Binance futures public data request failed: {type(exc).__name__}") from exc


def _finite(value: Any, field: str, *, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError(f"invalid {field}")
    return number


def fetch_futures_klines(
    symbol: str, interval: str, *, limit: int = 1000,
    start_ms: int | None = None, end_ms: int | None = None,
    get_json: Callable[..., Any] = _get_json, timeout: float = 20.0,
) -> list[FuturesCandle]:
    if not symbol or interval not in PERIOD_MS:
        raise ValueError("symbol and a supported futures interval are required")
    if not 1 <= int(limit) <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if start_ms is not None and int(start_ms) < 0:
        raise ValueError("start_ms must be non-negative")
    if end_ms is not None and (start_ms is not None and int(end_ms) <= int(start_ms)):
        raise ValueError("end_ms must be later than start_ms")
    params: dict[str, Any] = {"symbol": symbol.upper(), "interval": interval, "limit": int(limit)}
    if start_ms is not None:
        params["startTime"] = int(start_ms)
    if end_ms is not None:
        params["endTime"] = int(end_ms)
    raw = get_json(KLINES_URL, params, timeout=timeout)
    if not isinstance(raw, list):
        raise ValueError("unexpected futures kline response")
    candles = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 11:
            continue
        candle = FuturesCandle(
            symbol.upper(), int(row[0]), int(row[6]),
            _finite(row[1], "open", minimum=0.0),
            _finite(row[2], "high", minimum=0.0),
            _finite(row[3], "low", minimum=0.0),
            _finite(row[4], "close", minimum=0.0),
            _finite(row[5], "volume", minimum=0.0),
            _finite(row[7], "quote_volume", minimum=0.0),
            _finite(row[10], "taker_buy_quote_volume", minimum=0.0),
            int(row[8]),
        )
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            raise ValueError("futures candle prices must be positive")
        if candle.high < max(candle.open, candle.close, candle.low):
            raise ValueError("inconsistent futures candle OHLC values")
        if candle.low > min(candle.open, candle.close, candle.high):
            raise ValueError("inconsistent futures candle OHLC values")
        candles.append(candle)
    candles.sort(key=lambda item: item.open_time_ms)
    by_time = {item.open_time_ms: item for item in candles}
    return list(by_time.values())


def fetch_open_interest_history(
    symbol: str, period: str, start_ms: int, end_ms: int, *,
    get_json: Callable[..., Any] = _get_json, timeout: float = 20.0,
    page_limit: int = 500,
) -> list[OpenInterestSnapshot]:
    if not symbol or period not in PERIOD_MS or int(start_ms) < 0 or int(end_ms) <= int(start_ms):
        raise ValueError("symbol, supported period, and valid time range are required")
    if not 1 <= int(page_limit) <= 500:
        raise ValueError("open-interest page_limit must be between 1 and 500")
    rows: list[OpenInterestSnapshot] = []
    cursor = int(start_ms)
    while cursor <= int(end_ms):
        raw = get_json(OPEN_INTEREST_URL, {
            "symbol": symbol.upper(), "period": period,
            "startTime": cursor, "endTime": int(end_ms), "limit": int(page_limit),
        }, timeout=timeout)
        if not isinstance(raw, list):
            raise ValueError("unexpected open-interest response")
        parsed = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            timestamp = int(item["timestamp"])
            if int(start_ms) <= timestamp <= int(end_ms):
                parsed.append(OpenInterestSnapshot(
                    symbol.upper(), timestamp,
                    _finite(item.get("sumOpenInterest"), "sumOpenInterest", minimum=0.0),
                    _finite(item.get("sumOpenInterestValue"), "sumOpenInterestValue", minimum=0.0)
                    if item.get("sumOpenInterestValue") is not None else None,
                ))
        if not parsed:
            break
        rows.extend(parsed)
        last_ts = max(x.timestamp_ms for x in parsed)
        if last_ts >= int(end_ms) or len(raw) < int(page_limit):
            break
        next_cursor = last_ts + 1
        if next_cursor <= cursor:
            raise RuntimeError("open-interest pagination did not advance")
        cursor = next_cursor
    by_time = {item.timestamp_ms: item for item in rows}
    return [by_time[k] for k in sorted(by_time)]


def fetch_funding_rate_history(
    symbol: str, start_ms: int, end_ms: int, *,
    get_json: Callable[..., Any] = _get_json, timeout: float = 20.0,
    page_limit: int = 1000,
) -> list[FundingEvent]:
    if not symbol or int(start_ms) < 0 or int(end_ms) <= int(start_ms):
        raise ValueError("symbol and valid funding time range are required")
    if not 1 <= int(page_limit) <= 1000:
        raise ValueError("funding page_limit must be between 1 and 1000")
    rows: list[FundingEvent] = []
    cursor = int(start_ms)
    while cursor <= int(end_ms):
        raw = get_json(FUNDING_URL, {
            "symbol": symbol.upper(), "startTime": cursor,
            "endTime": int(end_ms), "limit": int(page_limit),
        }, timeout=timeout)
        if not isinstance(raw, list):
            raise ValueError("unexpected funding-rate response")
        parsed = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            timestamp = int(item["fundingTime"])
            rate = _finite(item.get("fundingRate"), "fundingRate")
            if not -1.0 <= rate <= 1.0:
                raise ValueError("funding rate outside defensive bounds")
            if int(start_ms) <= timestamp <= int(end_ms):
                parsed.append(FundingEvent(symbol.upper(), timestamp, rate))
        if not parsed:
            break
        rows.extend(parsed)
        last_ts = max(x.timestamp_ms for x in parsed)
        if last_ts >= int(end_ms) or len(raw) < int(page_limit):
            break
        next_cursor = last_ts + 1
        if next_cursor <= cursor:
            raise RuntimeError("funding pagination did not advance")
        cursor = next_cursor
    by_time = {item.timestamp_ms: item for item in rows}
    return [by_time[k] for k in sorted(by_time)]


def _last_strictly_before(items, timestamp_ms: int, key: str):
    candidate = None
    for item in items:
        if int(getattr(item, key)) >= int(timestamp_ms):
            break
        candidate = item
    return candidate


def project60_rows(
    candles: list[FuturesCandle],
    open_interest: list[OpenInterestSnapshot],
    funding: list[FundingEvent],
    *,
    oi_max_age_ms: int = 2 * 60 * 60 * 1000,
    funding_max_age_ms: int = 9 * 60 * 60 * 1000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build Project60-compatible JSONL rows with strict backward as-of joins."""
    ordered_oi = sorted(open_interest, key=lambda x: x.timestamp_ms)
    ordered_funding = sorted(funding, key=lambda x: x.timestamp_ms)
    output = []
    oi_count = funding_count = 0
    for candle in sorted(candles, key=lambda x: x.open_time_ms):
        oi = _last_strictly_before(ordered_oi, candle.close_time_ms, "timestamp_ms")
        fund = _last_strictly_before(ordered_funding, candle.close_time_ms, "timestamp_ms")
        oi_count += oi is not None
        funding_count += fund is not None
        close_ts = int(candle.close_time_ms)
        derivatives = {
            "oi_timestamp_ms": int(oi.timestamp_ms) if oi else None,
            "funding_timestamp_ms": int(fund.timestamp_ms) if fund else None,
            "oi_age_ms": close_ts - int(oi.timestamp_ms) if oi else None,
            "funding_age_ms": close_ts - int(fund.timestamp_ms) if fund else None,
            "oi_max_age_ms": int(oi_max_age_ms),
            "funding_max_age_ms": int(funding_max_age_ms),
        }
        output.append({
            "timestamp": close_ts,
            "coins": {
                candle.symbol: {
                    "price": candle.close,
                    "open": candle.open, "high": candle.high, "low": candle.low,
                    "volume": candle.volume,
                    "open_interest": oi.open_interest if oi else None,
                    "funding": fund.rate if fund else None,
                    "trades": {
                        "buy_usd": candle.taker_buy_quote_volume,
                        "sell_usd": max(0.0, candle.quote_volume - candle.taker_buy_quote_volume),
                    },
                    "orderbook": {"bid_usd": None, "ask_usd": None},
                    "derivatives": derivatives,
                }
            },
        })
    total = len(output)
    coverage = {
        "venue": "Binance USD-M Futures",
        "instrument": "perpetual",
        "bars": total,
        "oi_present": oi_count,
        "oi_coverage_pct": round(100.0 * oi_count / total, 4) if total else 0.0,
        "funding_present": funding_count,
        "funding_coverage_pct": round(100.0 * funding_count / total, 4) if total else 0.0,
        "oi_snapshots_fetched": len(open_interest),
        "funding_events_fetched": len(funding),
        "alignment": "strictly_before_candle_close_no_lookahead",
        "features_enabled": False,
    }
    return output, coverage


def download_project60(
    symbol: str = "BTCUSDT", interval: str = "1h", bars: int = 1000,
    out: str = "data/real/futures_project60.jsonl", *,
    get_json: Callable[..., Any] = _get_json, timeout: float = 20.0,
    overwrite: bool = False,
) -> tuple[Path, dict[str, Any]]:
    if not 1 <= int(bars) <= 1000:
        raise ValueError("bars must be between 1 and 1000")
    target = Path(out)
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing data file: {target}")
    candles = fetch_futures_klines(
        symbol, interval, limit=bars, get_json=get_json, timeout=timeout
    )
    if not candles:
        raise RuntimeError("Binance Futures returned no candles")
    start_ms = candles[0].open_time_ms
    end_ms = candles[-1].close_time_ms
    oi = fetch_open_interest_history(
        symbol, interval, start_ms, end_ms, get_json=get_json, timeout=timeout
    )
    funding = fetch_funding_rate_history(
        symbol, start_ms, end_ms, get_json=get_json, timeout=timeout
    )
    rows, coverage = project60_rows(
        candles, oi, funding, oi_max_age_ms=2 * PERIOD_MS[interval]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    coverage["output"] = str(target)
    return target, coverage


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download Binance USD-M Futures data for Project60 research")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", choices=tuple(PERIOD_MS), default="1h")
    parser.add_argument("--bars", type=int, default=1000)
    parser.add_argument("--out", default="data/real/futures_project60.jsonl")
    parser.add_argument("--overwrite", action="store_true", help="explicitly replace an existing output file")
    args = parser.parse_args(argv)
    path, coverage = download_project60(
        args.symbol, args.interval, args.bars, args.out, overwrite=args.overwrite
    )
    print(json.dumps({"path": str(path), "coverage": coverage}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
