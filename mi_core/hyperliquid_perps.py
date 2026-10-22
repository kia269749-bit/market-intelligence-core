"""Read-only public Hyperliquid perpetual market-data adapter.

Market observations come from Hyperliquid. Trading-cost estimates deliberately remain
centralized on the LBank Futures profile in central_config/trade_economics.
No account endpoints or order-placement endpoints are used.
"""
from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen

from .central_config import load_settings

INFO_URL = "https://api.hyperliquid.xyz/info"


def _post(payload: dict, timeout: int = 8):
    request = Request(
        INFO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "market-intelligence-core/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _coin(symbol: str) -> str:
    value = str(symbol).upper().replace("/", "").replace("-", "").replace("_", "")
    if value.endswith("USDT"):
        value = value[:-4]
    elif value.endswith("USDC"):
        value = value[:-4]
    return value


def fetch_snapshot(symbols=None, timeout: int = 8) -> dict:
    """Fetch current public Hyperliquid perp metadata and asset contexts."""
    settings = load_settings()
    requested = [_coin(s) for s in (symbols or settings.symbols)]
    if not requested or any(not s for s in requested):
        raise ValueError("symbols must be a non-empty list of valid symbols")

    payload = _post({"type": "metaAndAssetCtxs"}, timeout=timeout)
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("Hyperliquid metaAndAssetCtxs returned an unknown schema")
    meta, contexts = payload[0], payload[1]
    universe = meta.get("universe") if isinstance(meta, dict) else None
    if not isinstance(universe, list) or not isinstance(contexts, list):
        raise RuntimeError("Hyperliquid metadata/context arrays are missing")

    by_coin = {}
    for item, ctx in zip(universe, contexts):
        if not isinstance(item, dict) or not isinstance(ctx, dict):
            continue
        coin = str(item.get("name") or "").upper()
        if coin:
            by_coin[coin] = ctx

    rows, errors = [], []
    for symbol in requested:
        ctx = by_coin.get(symbol)
        if not ctx:
            errors.append({"exchange": "hyperliquid", "symbol": symbol, "error": "perp_not_found"})
            continue
        try:
            mark = float(ctx.get("markPx") or ctx.get("midPx") or 0)
            prev = float(ctx.get("prevDayPx") or 0)
        except (TypeError, ValueError):
            mark, prev = 0.0, 0.0
        if mark <= 0:
            errors.append({"exchange": "hyperliquid", "symbol": symbol, "error": "invalid_mark_price"})
            continue
        try:
            oi = float(ctx.get("openInterest")) if ctx.get("openInterest") is not None else None
        except (TypeError, ValueError):
            oi = None
        try:
            funding = float(ctx.get("funding")) if ctx.get("funding") is not None else None
        except (TypeError, ValueError):
            funding = None
        rows.append({
            "exchange": "hyperliquid",
            "market": "perpetuals",
            "symbol": symbol,
            "price": mark,
            "mark_price": mark,
            "open_interest": oi,
            "funding_rate": funding,
            "change_24h_pct": (mark / prev - 1.0) * 100.0 if prev > 0 else None,
            "source": "hyperliquid_metaAndAssetCtxs",
            "timestamp": int(time.time()),
        })

    status = "HEALTHY" if len(rows) == len(requested) else ("UNSAFE" if not rows else "DEGRADED")
    return {
        "ts_ms": int(time.time() * 1000),
        "exchange": "hyperliquid",
        "market": "perpetuals",
        "product_group": "perp",
        "rows": rows,
        "errors": errors,
        "data_quality": {
            "status": status,
            "expected_sources": len(requested),
            "successful_sources": len(rows),
            "success_ratio": len(rows) / len(requested),
            "healthy_symbols": len(rows) if status == "HEALTHY" else 0,
            "degraded_symbols": len(rows) if status == "DEGRADED" else 0,
            "unsafe_symbols": len(requested) - len(rows),
            "exchange_errors": {"hyperliquid": len(errors)} if errors else {},
        },
        "cost_model_exchange": "lbank",
        "cost_model_market": "futures",
        "research_only": True,
        "live_orders": False,
    }


def fetch_orderbook(symbol: str, depth: int = 20, timeout: int = 8) -> dict:
    """Fetch a public Hyperliquid L2 book; depth is limited by the public API."""
    coin = _coin(symbol)
    if not coin:
        raise ValueError("symbol must be non-empty")
    if not 1 <= int(depth) <= 20:
        raise ValueError("depth must be between 1 and 20")
    payload = _post({"type": "l2Book", "coin": coin}, timeout=timeout)
    if not isinstance(payload, dict) or not isinstance(payload.get("levels"), list) or len(payload["levels"]) != 2:
        raise RuntimeError("Hyperliquid l2Book returned an unknown schema")
    sides = []
    for raw_side in payload["levels"]:
        parsed = []
        for item in raw_side[:int(depth)]:
            if not isinstance(item, dict):
                continue
            try:
                price, size = float(item["px"]), float(item["sz"])
            except (KeyError, TypeError, ValueError):
                continue
            if price > 0 and size >= 0:
                parsed.append({"price": price, "size": size, "orders": item.get("n")})
        sides.append(parsed)
    bids, asks = sides
    if not bids or not asks:
        raise RuntimeError("Hyperliquid l2Book returned no valid bid/ask levels")
    bid, ask = bids[0]["price"], asks[0]["price"]
    mid = (bid + ask) / 2.0
    return {
        "ts_ms": int(payload.get("time") or time.time() * 1000),
        "exchange": "hyperliquid",
        "market": "perpetuals",
        "symbol": coin,
        "source": "hyperliquid_l2Book",
        "bids": bids,
        "asks": asks,
        "best_bid": bid,
        "best_ask": ask,
        "mid_price": mid,
        "spread_pct": (ask - bid) / mid * 100.0,
        "data_quality": "HEALTHY" if bid < ask else "CROSSED_OR_LOCKED",
        "cost_model_exchange": "lbank",
        "cost_model_market": "futures",
        "research_only": True,
        "live_orders": False,
    }
