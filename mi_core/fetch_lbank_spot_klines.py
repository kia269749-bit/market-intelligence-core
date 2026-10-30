"""Fetch public LBank SPOT candles into Project60-compatible JSONL.

Important: this uses the documented spot /v2/kline.do endpoint. The public
LBank CONTRACT API documentation currently exposes contract instruments,
quotes and order book, but not a historical contract-kline endpoint. Do not
label this spot dataset as futures data or mix it with Hyperliquid perps.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.lbank.info/v2/kline.do"
INTERVALS = {
    "1m": "minute1", "5m": "minute5", "15m": "minute15",
    "30m": "minute30", "1h": "hour1", "4h": "hour4", "1d": "day1",
}


def fetch(symbol="btc_usdt", interval="1h", limit=1000, timeout=20):
    if interval not in INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 1 <= int(limit) <= 2000:
        raise ValueError("limit must be between 1 and 2000")
    params = urlencode({"symbol": symbol.lower(), "size": int(limit),
                        "type": INTERVALS[interval], "time": int(time.time())})
    request = Request(f"{BASE_URL}?{params}", headers={"User-Agent": "market-intelligence-core/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if str(payload.get("result", "")).lower() != "true" or int(payload.get("error_code", -1)) != 0:
        raise RuntimeError(f"LBank API error: {payload.get('error_code')} {payload.get('msg')}")
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("LBank returned no candle rows")
    parsed = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        ts = int(float(row[0])) * 1000
        o, h, low, close, volume = map(float, row[1:6])
        if min(o, h, low, close) <= 0 or h < max(o, close, low) or low > min(o, close):
            raise ValueError(f"invalid OHLC candle at {ts}")
        parsed.append((ts, o, h, low, close, volume))
    parsed.sort(key=lambda x: x[0])
    if len({x[0] for x in parsed}) != len(parsed):
        raise ValueError("duplicate candle timestamps returned by LBank")
    return parsed


def write_jsonl(rows, symbol, interval, output):
    # The loader consumes timestamp + coins[symbol].price. OHLCV is retained
    # alongside price for provenance/future evaluators, but not silently used.
    asset = symbol.upper().replace("_", "")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for ts, o, h, low, close, volume in rows:
            item = {
                "timestamp": ts,
                "source": "lbank_spot_public_kline",
                "market_type": "spot",
                "symbol": asset,
                "interval": interval,
                "coins": {asset: {"price": close, "open": o, "high": h,
                                  "low": low, "close": close, "volume": volume}},
            }
            handle.write(json.dumps(item, separators=(",", ":")) + "\n")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="btc_usdt", help="LBank spot symbol, e.g. btc_usdt")
    parser.add_argument("--interval", choices=sorted(INTERVALS), default="1h")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--out", default="data/lbank_spot_btc_1h.jsonl")
    args = parser.parse_args(argv)
    rows = fetch(args.symbol, args.interval, args.limit)
    path = write_jsonl(rows, args.symbol, args.interval, args.out)
    print(json.dumps({"file": str(path), "candles": len(rows), "symbol": args.symbol,
                      "interval": args.interval, "market_type": "spot",
                      "first_ts_ms": rows[0][0], "last_ts_ms": rows[-1][0],
                      "source": BASE_URL}, indent=2))


if __name__ == "__main__":
    main()
