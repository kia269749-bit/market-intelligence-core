import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import MarketBar
from .storage import append_jsonl

BASE_URL = "https://data-api.binance.vision/api/v3/klines"

INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000,
}

def _get(params, timeout=20):
    query = urlencode(params)
    req = Request(BASE_URL + "?" + query, headers={"User-Agent": "market-intelligence-core/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def fetch_klines(symbol="BTCUSDT", interval="1h", limit=1000, start_ms=None, end_ms=None):
    symbol = symbol.upper()
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_ms is not None:
        params["startTime"] = int(start_ms)
    if end_ms is not None:
        params["endTime"] = int(end_ms)
    rows = _get(params)
    if not isinstance(rows, list):
        raise RuntimeError(f"unexpected Binance response: {rows}")
    return rows

def rows_to_bars(rows, symbol, now_ms=None):
    """Convert Binance klines, optionally excluding candles not yet closed."""
    from math import isfinite

    bars = []
    for r in rows:
        try:
            if len(r) < 11:
                continue

            ts = int(r[0])
            close_price = float(r[4])
            volume = float(r[5])
            close_time = int(r[6])
            taker_buy = float(r[9])
            try:
                o_, h_, l_ = float(r[1]), float(r[2]), float(r[3])
                ohlc_ok = (all(isfinite(x) and x > 0 for x in (o_, h_, l_))
                           and l_ <= min(o_, close_price) and h_ >= max(o_, close_price))
            except (TypeError, ValueError):
                ohlc_ok = False

            if now_ms is not None and close_time >= int(now_ms):
                continue

            if not all(isfinite(x) for x in
                       (close_price, volume, taker_buy)):
                continue
            if close_price <= 0 or volume < 0:
                continue
            if taker_buy < 0 or taker_buy > volume:
                continue

            bars.append(MarketBar(
                ts=ts,
                symbol=symbol.upper(),
                price=close_price,
                volume=volume,
                buy_volume=taker_buy,
                sell_volume=volume - taker_buy,
                open=o_ if ohlc_ok else None,
                high=h_ if ohlc_ok else None,
                low=l_ if ohlc_ok else None,
            ))
        except (TypeError, ValueError, IndexError, OverflowError):
            continue

    return bars


def download(symbol="BTCUSDT", interval="1h", bars=1000, out="data/real/btcusdt_1h.jsonl", sleep_s=0.15):
    if bars < 1:
        raise ValueError("bars must be positive")
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")

    remaining = bars
    reference_now_ms = int(time.time() * 1000)
    end_ms = reference_now_ms
    all_bars = []

    while remaining > 0:
        take = min(1000, remaining)
        rows = fetch_klines(symbol, interval, take, end_ms=end_ms)

        if not rows:
            break

        # Count only closed, valid candles, but paginate using raw rows.
        chunk = rows_to_bars(rows, symbol, now_ms=reference_now_ms)
        if chunk:
            all_bars.extend(chunk)

        unique = {bar.ts: bar for bar in all_bars}
        remaining = max(0, bars - len(unique))

        # Move backwards using the oldest raw kline, even if the newest
        # candle was filtered out because it is still open.
        raw_timestamps = []
        for row in rows:
            try:
                raw_timestamps.append(int(row[0]))
            except (TypeError, ValueError, IndexError, OverflowError):
                continue

        if not raw_timestamps:
            break

        oldest_ts = min(raw_timestamps)
        if oldest_ts >= end_ms:
            break
        end_ms = oldest_ts - 1

        # A short raw response means the API has no more rows for this page.
        if len(rows) < take:
            break

        if remaining > 0:
            time.sleep(max(0.0, sleep_s))

    unique = {bar.ts: bar for bar in all_bars}
    result = [unique[ts] for ts in sorted(unique)][-bars:]

    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    for bar in result:
        append_jsonl(path, bar.to_dict())

    return result, path
