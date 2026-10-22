"""Compatibility facade with separate market-data and cost-model venues.

Default market observations come from Hyperliquid perpetuals. Transaction costs remain
the centrally configured LBank Futures assumptions. No venue blending or fallback.
"""
from __future__ import annotations

from .central_config import load_settings
from .hyperliquid_perps import fetch_snapshot as _fetch_hyperliquid_snapshot
from .lbank_futures import fetch_snapshot as _fetch_lbank_snapshot

_settings = load_settings()
DEFAULT_SYMBOLS = list(_settings.symbols)
EXCHANGES = (_settings.data_exchange,)


def fetch_snapshot(symbols=None, exchanges=None):
    requested = tuple(str(x).lower() for x in (exchanges or EXCHANGES))
    if requested != EXCHANGES:
        raise ValueError(
            "configured market-data source is {}; cross-exchange fallback is disabled".format(
                ",".join(EXCHANGES)
            )
        )
    if _settings.data_exchange == "hyperliquid":
        return _fetch_hyperliquid_snapshot(symbols=symbols)
    if _settings.data_exchange == "lbank":
        return _fetch_lbank_snapshot(symbols=symbols)
    raise RuntimeError("unsupported configured market-data source")


def print_snapshot(snapshot):
    source = snapshot.get("exchange", "unknown").upper()
    market = snapshot.get("market", "unknown")
    print("\\n{} {} | ts_ms={}".format(source, market, snapshot.get("ts_ms")))
    print("market_data_exchange={} | cost_model_exchange={} | cost_model_market={}".format(
        snapshot.get("exchange", "unknown"),
        snapshot.get("cost_model_exchange", _settings.exchange),
        snapshot.get("cost_model_market", _settings.market),
    ))
    quality = snapshot.get("data_quality", {})
    print("data_quality={} | symbols={}/{}".format(
        quality.get("status", "UNKNOWN"),
        quality.get("successful_sources", 0),
        quality.get("expected_sources", 0)))
    print("SYMBOL       LAST/MARK PRICE       OPEN INTEREST       FUNDING")
    for row in snapshot.get("rows", []):
        print("{:<12}{:>16.8g}  {:>16}  {:>12}".format(
            row.get("symbol", ""),
            float(row.get("price", 0.0)),
            "-" if row.get("open_interest") is None else "{:.8g}".format(row["open_interest"]),
            "-" if row.get("funding_rate") is None else "{:.8g}".format(row["funding_rate"])))
    for error in snapshot.get("errors", []):
        print("DATA_ERROR {} {} {}".format(
            error.get("exchange", source.lower()), error.get("symbol", ""), error.get("error", "unknown")))
