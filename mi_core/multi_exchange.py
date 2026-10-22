"""Compatibility facade for the centralized LBank futures market-data source.

The legacy module name remains to avoid breaking imports, but the default and only
supported source is LBank USDT-margined futures. No cross-exchange median or silent
fallback is permitted.
"""
from __future__ import annotations

from .central_config import load_settings
from .lbank_futures import fetch_snapshot as _fetch_lbank_snapshot

_settings = load_settings()
DEFAULT_SYMBOLS = list(_settings.symbols)
EXCHANGES = ("lbank",)


def fetch_snapshot(symbols=None, exchanges=None):
    requested_exchanges = tuple(str(x).lower() for x in (exchanges or EXCHANGES))
    if requested_exchanges != ("lbank",):
        raise ValueError("central source is LBank futures only; other exchanges are disabled")
    return _fetch_lbank_snapshot(symbols=symbols)


def print_snapshot(snapshot):
    print("\nLBank FUTURES | ts_ms={}".format(snapshot.get("ts_ms")))
    print("exchange=lbank | market=futures | product_group={}".format(snapshot.get("product_group")))
    quality = snapshot.get("data_quality", {})
    print("data_quality={} | symbols={}/{}".format(
        quality.get("status", "UNKNOWN"),
        quality.get("successful_sources", 0),
        quality.get("expected_sources", 0)))
    print("SYMBOL       LAST PRICE          MARK PRICE         FUNDING")
    for row in snapshot.get("rows", []):
        print("{:<12}{:>16.8g}  {:>16}  {:>12}".format(
            row.get("symbol", ""),
            float(row.get("price", 0.0)),
            "-" if row.get("mark_price") is None else "{:.8g}".format(row["mark_price"]),
            "-" if row.get("funding_rate") is None else "{:.8g}".format(row["funding_rate"])))
    for error in snapshot.get("errors", []):
        print("DATA_ERROR {} {} {}".format(
            error.get("exchange", "lbank"), error.get("symbol", ""), error.get("error", "unknown")))
