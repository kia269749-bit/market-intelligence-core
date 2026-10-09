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

def fetch_klines(symbol="BTCUSDT", interval="1h", limit=1000, start_ms=None, end_ms=None, timeout=20):
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
    rows = _get(params, timeout=timeout)
    if not isinstance(rows, list):
        raise RuntimeError(f"unexpected Binance response: {rows}")
    return rows

def rows_to_bars(rows, symbol):
    bars = []
    for r in rows:
        if len(r) < 11:
            continue
        volume = float(r[5])
        taker_buy = float(r[9])
        bars.append(MarketBar(
            ts=int(r[0]),
            symbol=symbol.upper(),
            price=float(r[4]),
            volume=volume,
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            buy_volume=taker_buy,
            sell_volume=max(0.0, volume - taker_buy),
        ))
    return bars

def download(symbol="BTCUSDT", interval="1h", bars=1000, out="data/real/btcusdt_1h.jsonl", sleep_s=0.15):
    if bars < 1:
        raise ValueError("bars must be positive")
    step = INTERVAL_MS[interval]
    remaining = bars
    end_ms = int(time.time() * 1000)
    all_bars = []
    while remaining:
        take = min(1000, remaining)
        rows = fetch_klines(symbol, interval, take, end_ms=end_ms)
        chunk = rows_to_bars(rows, symbol)
        if not chunk:
            break
        all_bars = chunk + all_bars
        remaining -= len(chunk)
        end_ms = chunk[0].ts - 1
        if len(chunk) < take:
            break
        if remaining:
            time.sleep(max(0.0, sleep_s))
    # Deduplicate by timestamp and keep chronological order.
    unique = {b.ts: b for b in all_bars}
    result = [unique[k] for k in sorted(unique)]
    result = result[-bars:]
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    for bar in result:
        append_jsonl(path, bar.to_dict())
    return result, path
