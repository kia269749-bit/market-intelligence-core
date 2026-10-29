"""Read-only Hyperliquid perpetual historical-data adapter.

Uses the public /info endpoint only. No wallet, credentials, order or account API.
Historical candles do not contain executable bid/ask history, so candle-derived
slippage must be labelled as a model assumption, never as observed execution.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

INFO_URL = "https://api.hyperliquid.xyz/info"


@dataclass(frozen=True)
class PerpCandle:
    coin: str
    timestamp_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


@dataclass(frozen=True)
class FundingEvent:
    coin: str
    timestamp_ms: int
    rate: float


def _post_info(payload: dict[str, Any], timeout: float = 20.0) -> Any:
    request = Request(
        INFO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "market-intelligence-core-research/1"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Hyperliquid info endpoint returned HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Hyperliquid public data request failed: {type(exc).__name__}") from exc


def _positive_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def fetch_candles(
    coin: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    *,
    post_json: Callable[[dict[str, Any]], Any] = _post_info,
) -> list[PerpCandle]:
    """Fetch historical perpetual candles from Hyperliquid's public info API."""
    if not coin or not interval:
        raise ValueError("coin and interval are required")
    if int(start_ms) < 0 or int(end_ms) <= int(start_ms):
        raise ValueError("end_ms must be greater than non-negative start_ms")
    payload = {
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": int(start_ms), "endTime": int(end_ms)},
    }
    raw = post_json(payload)
    if not isinstance(raw, list):
        raise ValueError("unexpected candle response: expected a list")
    candles: list[PerpCandle] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        candle = PerpCandle(
            coin=coin,
            timestamp_ms=int(row.get("t")),
            close_time_ms=int(row.get("T", row.get("t"))),
            open=_positive_float(row.get("o"), "open"),
            high=_positive_float(row.get("h"), "high"),
            low=_positive_float(row.get("l"), "low"),
            close=_positive_float(row.get("c"), "close"),
            volume=float(row.get("v", 0) or 0),
            trades=int(row.get("n", 0) or 0),
        )
        if candle.high < max(candle.open, candle.close, candle.low) or candle.low > min(candle.open, candle.close, candle.high):
            raise ValueError("inconsistent candle OHLC values")
        candles.append(candle)
    candles.sort(key=lambda item: item.timestamp_ms)
    deduped: dict[int, PerpCandle] = {item.timestamp_ms: item for item in candles}
    return list(deduped.values())


def fetch_funding_history(
    coin: str,
    start_ms: int,
    end_ms: int,
    *,
    post_json: Callable[[dict[str, Any]], Any] = _post_info,
) -> list[FundingEvent]:
    """Fetch realized historical funding rates; each row is a discrete funding event."""
    if not coin or int(start_ms) < 0 or int(end_ms) <= int(start_ms):
        raise ValueError("coin and valid time range are required")
    # Funding history can be capped per response. Query 14-day windows (about
    # 336 hourly events) so long backtests do not silently stop at a page limit.
    max_window_ms = 14 * 24 * 60 * 60 * 1000
    events: list[FundingEvent] = []
    cursor = int(start_ms)
    while cursor <= int(end_ms):
        chunk_end = min(cursor + max_window_ms, int(end_ms))
        raw = post_json({
            "type": "fundingHistory", "coin": coin,
            "startTime": cursor, "endTime": chunk_end,
        })
        if not isinstance(raw, list):
            raise ValueError("unexpected funding response: expected a list")
        for row in raw:
            if not isinstance(row, dict):
                continue
            rate = float(row["fundingRate"])
            if not (-1.0 <= rate <= 1.0):
                raise ValueError("funding rate outside defensive bounds")
            timestamp_ms = int(row["time"])
            if int(start_ms) <= timestamp_ms <= int(end_ms):
                events.append(FundingEvent(coin, timestamp_ms, rate))
        if chunk_end >= int(end_ms):
            break
        cursor = chunk_end + 1
    events.sort(key=lambda item: item.timestamp_ms)
    by_time = {item.timestamp_ms: item for item in events}
    return list(by_time.values())


def join_funding_feature(candles: list[PerpCandle], events: list[FundingEvent]) -> list[float | None]:
    """For model features only: carry forward the last known rate without look-ahead.

    This is not a funding cashflow calculation. Realized payments must use the
    discrete events inside each position's actual holding interval.
    """
    ordered = sorted(events, key=lambda item: item.timestamp_ms)
    j = 0
    latest: float | None = None
    out = []
    for candle in sorted(candles, key=lambda item: item.timestamp_ms):
        # A candle's close is only available at close_time_ms. Strictly exclude
        # an event at that exact timestamp because ordering may be ambiguous.
        while j < len(ordered) and ordered[j].timestamp_ms < candle.close_time_ms:
            latest = ordered[j].rate
            j += 1
        out.append(latest)
    return out


def funding_cost_pct(
    side: int,
    position_size: float,
    oracle_prices_and_rates: list[tuple[float, float]],
    *,
    entry_oracle_price: float | None = None,
) -> float:
    """Funding cost as percent of constant position notional over discrete events.

    side=+1 for long and -1 for short. Positive output is a cost; negative is
    a funding credit. Hyperliquid uses oracle price for the payment notional.
    Caller must supply the oracle price at each event; candle close is only a
    proxy if the true historical oracle price is unavailable.
    """
    if side not in (-1, 1):
        raise ValueError("side must be +1 (long) or -1 (short)")
    if position_size <= 0:
        raise ValueError("position_size must be positive")
    if not oracle_prices_and_rates:
        return 0.0
    reference_price = entry_oracle_price if entry_oracle_price is not None else oracle_prices_and_rates[0][0]
    if reference_price <= 0:
        raise ValueError("entry oracle price must be positive")
    initial_notional = reference_price * position_size
    cash_cost = 0.0
    for price, rate in oracle_prices_and_rates:
        if price <= 0 or not (-1.0 <= rate <= 1.0):
            raise ValueError("invalid oracle price or funding rate")
        cash_cost += side * position_size * price * rate
    return cash_cost / initial_notional * 100.0
