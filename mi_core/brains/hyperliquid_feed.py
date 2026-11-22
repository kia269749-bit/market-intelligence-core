"""Public read-only Hyperliquid market context for specialist brains."""
from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen

_INFO_URL = "https://api.hyperliquid.xyz/info"
_CACHE: dict[str, tuple[float, dict]] = {}
_OI_PREVIOUS: dict[str, tuple[int, float, float]] = {}


def _post(payload: dict, timeout: float = 6.0):
    request = Request(
        _INFO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Project60-ResearchBrain/1"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_hyperliquid_brain_context(coin: str = "BTC", now_ms: int | None = None,
                                    timeout: float = 6.0, force: bool = False) -> dict:
    """Fetch current L2, latest settled funding, and OI delta without credentials.

    The function is read-only and caches successful snapshots for 30 seconds.
    OI change is unavailable on the first observation because no baseline exists.
    """
    now_ms = int(time.time() * 1000 if now_ms is None else now_ms)
    coin = str(coin).upper()
    cached = _CACHE.get(coin)
    if not force and cached and time.monotonic() - cached[0] < 30:
        return dict(cached[1])

    result = {"orderbook": None, "funding_events": [], "open_interest": None,
              "source": "Hyperliquid public Info API", "timestamp_ms": now_ms}
    errors = {}

    try:
        raw_book = _post({"type": "l2Book", "coin": coin}, timeout)
        levels = raw_book.get("levels") if isinstance(raw_book, dict) else None
        if isinstance(levels, list) and len(levels) >= 2:
            bids = [[float(row["px"]), float(row["sz"])] for row in levels[0]
                    if isinstance(row, dict) and float(row.get("sz", 0)) > 0]
            asks = [[float(row["px"]), float(row["sz"])] for row in levels[1]
                    if isinstance(row, dict) and float(row.get("sz", 0)) > 0]
            book_ts = int(raw_book.get("time", now_ms))
            result["orderbook"] = {"timestamp_ms": book_ts, "bids": bids, "asks": asks}
    except Exception as exc:
        errors["orderbook"] = type(exc).__name__

    try:
        raw_funding = _post({
            "type": "fundingHistory", "coin": coin,
            "startTime": now_ms - 86_400_000, "endTime": now_ms,
        }, timeout)
        if isinstance(raw_funding, list):
            eligible = []
            for row in raw_funding:
                if not isinstance(row, dict):
                    continue
                try:
                    ts = int(row.get("time"))
                    rate = float(row.get("fundingRate"))
                except (TypeError, ValueError):
                    continue
                if ts <= now_ms:
                    eligible.append({"timestamp_ms": ts, "funding_rate": rate})
            if eligible:
                result["funding_events"] = [max(eligible, key=lambda row: row["timestamp_ms"])]
    except Exception as exc:
        errors["funding"] = type(exc).__name__

    try:
        meta_ctx = _post({"type": "metaAndAssetCtxs"}, timeout)
        if isinstance(meta_ctx, list) and len(meta_ctx) >= 2:
            meta, contexts = meta_ctx[0], meta_ctx[1]
            universe = meta.get("universe", []) if isinstance(meta, dict) else []
            index = next((i for i, item in enumerate(universe)
                          if isinstance(item, dict) and str(item.get("name", "")).upper() == coin), None)
            if index is not None and isinstance(contexts, list) and index < len(contexts):
                oi = float(contexts[index].get("openInterest"))
                mark = float(contexts[index].get("markPx"))
                if oi > 0 and mark > 0:
                    previous = _OI_PREVIOUS.get(coin)
                    if previous and now_ms > previous[0] and previous[1] > 0 and previous[2] > 0:
                        oi_change = (oi / previous[1] - 1.0) * 100.0
                        price_change = (mark / previous[2] - 1.0) * 100.0
                        result["open_interest"] = {
                            "timestamp_ms": now_ms,
                            "change_pct": oi_change,
                            "price_change_pct": price_change,
                            "open_interest": oi,
                            "mark_price": mark,
                        }
                    _OI_PREVIOUS[coin] = (now_ms, oi, mark)
    except Exception as exc:
        errors["open_interest"] = type(exc).__name__

    result["errors"] = errors
    result["available"] = any(result[key] for key in ("orderbook", "funding_events", "open_interest"))
    _CACHE[coin] = (time.monotonic(), result)
    return dict(result)


def fetch_hyperliquid_brain_contexts(coins=("BTC",), now_ms: int | None = None,
                                     timeout: float = 6.0) -> dict:
    """Fetch independent cached read-only market contexts for several coins."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    names = tuple(dict.fromkeys(str(coin).upper() for coin in coins if str(coin).strip()))
    results = {}
    if not names:
        return results
    with ThreadPoolExecutor(max_workers=min(5, len(names))) as pool:
        futures = {
            pool.submit(fetch_hyperliquid_brain_context, coin, now_ms, timeout): coin
            for coin in names
        }
        for future in as_completed(futures):
            coin = futures[future]
            try:
                results[coin] = future.result()
            except Exception as exc:
                results[coin] = {
                    "available": False,
                    "source": "Hyperliquid public Info API",
                    "errors": {"feed": type(exc).__name__},
                }
    return results
