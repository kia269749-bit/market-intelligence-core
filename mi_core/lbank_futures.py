"""Read-only public market-data adapter for LBank USDT-margined futures.

No spot API, other exchange, private endpoint, or trading endpoint is used here.
The adapter intentionally raises on missing/invalid data instead of silently falling
back to another venue.
"""
from __future__ import annotations

import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .central_config import load_settings

BASE_URL = "https://lbkperp.lbank.com/cfd/openApi/v1/pub"


def _get_json(url: str, params: dict | None = None, timeout: int = 8):
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    request = Request(url, headers={"User-Agent": "market-intelligence-core/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_symbol(value: str) -> str:
    return str(value).upper().replace("/", "").replace("-", "").replace("_", "").strip()


def _extract_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("list", "rows", "marketData", "result"):
                rows = data.get(key)
                if isinstance(rows, list):
                    return rows
    raise RuntimeError("LBank futures marketData response has an unknown schema")


def fetch_market_rows(timeout: int = 8) -> list[dict]:
    settings = load_settings()
    payload = _get_json(f"{BASE_URL}/marketData", {"productGroup": settings.product_group}, timeout)
    if isinstance(payload, dict):
        if payload.get("success") is False or payload.get("result") is False:
            raise RuntimeError(f"LBank futures API rejected request: {payload.get('msg', payload)}")
        if payload.get("error_code") not in (None, 0, "0"):
            raise RuntimeError(f"LBank futures API error: {payload.get('error_code')}: {payload.get('msg', '')}")
    rows = _extract_rows(payload)
    valid = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_symbol(row.get("symbol", ""))
        try:
            price = float(row.get("lastPrice"))
        except (TypeError, ValueError):
            continue
        if symbol and price > 0:
            valid.append({
                "exchange": "lbank",
                "market": "futures",
                "symbol": symbol,
                "price": price,
                "open_price": _optional_float(row.get("openPrice")),
                "change_24h_pct": _change_pct(row.get("lastPrice"), row.get("openPrice")),
                "mark_price": _optional_float(row.get("markedPrice")),
                "funding_rate": _optional_float(row.get("prePositionFeeRate")),
                "volume_24h": _optional_float(row.get("volume")),
                "turnover_24h": _optional_float(row.get("turnover")),
                "source": "lbank_contract_marketData",
            })
    if not valid:
        raise RuntimeError("LBank futures API returned no valid contract prices")
    return valid


def _change_pct(last, opened):
    last_value = _optional_float(last)
    open_value = _optional_float(opened)
    if last_value is None or open_value is None or open_value <= 0:
        return None
    return (last_value / open_value - 1.0) * 100.0


def _optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_snapshot(symbols=None, timeout: int = 8) -> dict:
    settings = load_settings()
    requested = [normalize_symbol(s) for s in (symbols or settings.symbols)]
    if not requested or any(not s for s in requested):
        raise ValueError("symbols must be a non-empty list of valid symbols")

    all_rows = fetch_market_rows(timeout=timeout)
    by_symbol = {row["symbol"]: row for row in all_rows}
    rows = []
    errors = []
    aggregates = []
    for symbol in requested:
        row = by_symbol.get(symbol)
        if row is None:
            errors.append({"exchange": "lbank", "symbol": symbol, "error": "contract_not_found"})
            continue
        rows.append(row)
        aggregates.append({
            "symbol": symbol,
            "sources": 1,
            "median_price": row["price"],
            "min_price": row["price"],
            "max_price": row["price"],
            "cross_exchange_spread_pct": 0.0,
            "exchange": "lbank",
            "market": "futures",
            "mark_price": row["mark_price"],
            "funding_rate": row["funding_rate"],
        })

    status = "HEALTHY" if len(rows) == len(requested) else ("UNSAFE" if not rows else "DEGRADED")
    return {
        "ts_ms": int(time.time() * 1000),
        "exchange": "lbank",
        "market": "futures",
        "product_group": settings.product_group,
        "rows": rows,
        "aggregates": aggregates,
        "errors": errors,
        "data_quality": {
            "status": status,
            "expected_sources": len(requested),
            "successful_sources": len(rows),
            "success_ratio": len(rows) / len(requested),
            "healthy_symbols": len(rows) if status == "HEALTHY" else 0,
            "degraded_symbols": len(rows) if status == "DEGRADED" else 0,
            "unsafe_symbols": len(requested) - len(rows),
            "exchange_errors": {"lbank": len(errors)} if errors else {},
        },
        "research_only": True,
        "live_orders": False,
    }
