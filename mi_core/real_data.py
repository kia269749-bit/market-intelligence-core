"""Historical market-data adapter.

Historical candles must come from the configured venue and market. The old
implementation silently fetched Binance spot klines, which is incompatible
with the LBank Futures research configuration. Until a documented public
LBank Futures candle endpoint is verified, this module fails closed.
"""
from __future__ import annotations

from pathlib import Path

from .models import MarketBar

INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000,
}


def fetch_klines(symbol="BTCUSDT", interval="1h", limit=1000, start_ms=None, end_ms=None):
    """Refuse to substitute another venue's spot candles for LBank Futures."""
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    raise RuntimeError(
        "LBank Futures historical candles are not wired: refusing Binance spot fallback. "
        "Verify and implement the official LBank contract candle endpoint before historical backtests."
    )


def rows_to_bars(rows, symbol):
    """Convert an already-fetched OHLCV array to MarketBar objects."""
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
            buy_volume=taker_buy,
            sell_volume=max(0.0, volume - taker_buy),
        ))
    return bars


def download(symbol="BTCUSDT", interval="1h", bars=1000,
             out="data/real/btcusdt_1h.jsonl", sleep_s=0.15):
    """Historical downloader intentionally blocks until LBank Futures is verified."""
    if bars < 1:
        raise ValueError("bars must be positive")
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")
    # Do not create/truncate files until the correct venue endpoint is implemented.
    fetch_klines(symbol=symbol, interval=interval, limit=min(1000, bars))
    raise AssertionError("fetch_klines should fail closed until LBank Futures candles are implemented")
