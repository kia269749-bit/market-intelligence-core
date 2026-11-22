"""Read-only OHLCV + derivatives feed and live brain runner for Hyperliquid."""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from typing import Iterable

from .contracts import MarketSnapshot
from .engine import evaluate_brains
from .hyperliquid_feed import _post, fetch_hyperliquid_brain_context

TIMEFRAME_MS = {
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}
ALLOWED_TIMEFRAMES = tuple(TIMEFRAME_MS)


def fetch_hyperliquid_ohlcv(
    coin: str,
    timeframe: str,
    *,
    bars: int = 200,
    now_ms: int | None = None,
    timeout: float = 8.0,
):
    """Fetch only completed Hyperliquid candles and return a timestamp-indexed DataFrame."""
    import pandas as pd

    coin = str(coin).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,20}", coin):
        raise ValueError("invalid Hyperliquid coin")
    if timeframe not in TIMEFRAME_MS:
        raise ValueError("timeframe must be one of 15m, 1h, 4h, 1d")
    if not 60 <= int(bars) <= 1000:
        raise ValueError("bars must be between 60 and 1000")
    now_ms = int(time.time() * 1000 if now_ms is None else now_ms)
    duration = TIMEFRAME_MS[timeframe]
    raw = _post({
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": timeframe,
            "startTime": now_ms - duration * (int(bars) + 3),
            "endTime": now_ms,
        },
    }, timeout=timeout)
    if not isinstance(raw, list):
        raise RuntimeError("Hyperliquid candleSnapshot returned a non-list response")

    rows_by_time = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            open_ms = int(item["t"])
            close_ms = int(item["T"])
            values = {
                "open": float(item["o"]),
                "high": float(item["h"]),
                "low": float(item["l"]),
                "close": float(item["c"]),
                "volume": float(item["v"]),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        prices = (values["open"], values["high"], values["low"], values["close"])
        if close_ms > now_ms:
            continue
        if not all(math.isfinite(value) for value in (*prices, values["volume"])):
            continue
        if min(prices) <= 0 or values["volume"] < 0:
            continue
        if values["high"] < max(values["open"], values["close"], values["low"]):
            continue
        if values["low"] > min(values["open"], values["close"], values["high"]):
            continue
        rows_by_time[open_ms] = values

    if len(rows_by_time) < 60:
        raise RuntimeError(f"insufficient_closed_candles:{timeframe}:{len(rows_by_time)}")
    ordered = sorted(rows_by_time.items())[-int(bars):]
    frame = pd.DataFrame(
        [values for _, values in ordered],
        index=[timestamp for timestamp, _ in ordered],
        columns=("open", "high", "low", "close", "volume"),
    )
    frame.index.name = "open_time_ms"
    return frame


def fetch_hyperliquid_market_snapshot(
    coin: str,
    *,
    bars: int = 200,
    timeout: float = 8.0,
) -> tuple[MarketSnapshot, dict]:
    """Build one brain snapshot using Hyperliquid candles, L2, funding and OI only."""
    frames = {}
    candle_errors = {}
    for timeframe in ALLOWED_TIMEFRAMES:
        try:
            frames[timeframe] = fetch_hyperliquid_ohlcv(
                coin, timeframe, bars=bars, timeout=timeout
            )
        except Exception as exc:
            candle_errors[timeframe] = type(exc).__name__

    context = fetch_hyperliquid_brain_context(
        coin, timeout=timeout, force=True
    )
    if not frames:
        raise RuntimeError("no_usable_hyperliquid_ohlcv:" + ",".join(sorted(candle_errors)))

    as_of_ms = int(time.time() * 1000)
    payload = {
        "ohlcv_by_timeframe": frames,
        "orderbook": context.get("orderbook"),
        "funding_events": context.get("funding_events", []),
        "open_interest": context.get("open_interest"),
        "hyperliquid_context": context,
        "feed_errors": candle_errors,
        "market_data_source": "Hyperliquid public Info API",
    }
    snapshot = MarketSnapshot(
        symbol=str(coin).upper(),
        as_of_ms=as_of_ms,
        timeframe="15m",
        payload=payload,
    )
    health = {
        "source": "Hyperliquid public Info API",
        "candles": {
            timeframe: {
                "closed_rows": int(len(frame)),
                "last_open_ms": int(frame.index[-1]),
                "last_close": float(frame["close"].iloc[-1]),
            }
            for timeframe, frame in frames.items()
        },
        "candle_errors": candle_errors,
        "orderbook_available": context.get("orderbook") is not None,
        "funding_events": len(context.get("funding_events", [])),
        "open_interest_available": context.get("open_interest") is not None,
        "context_errors": context.get("errors", {}),
    }
    return snapshot, health


def run_once(
    coins: Iterable[str] = ("BTC", "ETH", "SOL", "XRP", "DOGE"),
    *,
    bars: int = 200,
    timeout: float = 8.0,
) -> dict:
    """Fetch real public market data and evaluate the complete Project60 brain."""
    results = []
    for coin in tuple(dict.fromkeys(str(x).strip().upper() for x in coins if str(x).strip())):
        try:
            snapshot, health = fetch_hyperliquid_market_snapshot(
                coin, bars=bars, timeout=timeout
            )
            report = evaluate_brains(snapshot)
            specialists = [
                {
                    "brain_id": proposal.brain_id,
                    "family": proposal.family,
                    "direction": proposal.direction,
                    "confidence": proposal.confidence,
                    "available": proposal.available,
                    "reasons": list(proposal.reasons),
                    "source_ids": list(proposal.source_ids),
                }
                for proposal in report.specialist_proposals
            ]
            central = report.central_decision
            results.append({
                "symbol": coin,
                "status": "evaluated",
                "feed": health,
                "specialist_count": len(specialists),
                "specialists": specialists,
                "central": {
                    "decision": central.decision,
                    "confidence": central.confidence,
                    "supporting_families": list(central.supporting_families),
                    "reasons": list(central.reasons),
                    "weighted_win_rate": central.weighted_win_rate,
                    "research_only": central.research_only,
                    "live_orders": central.live_orders,
                },
            })
        except Exception as exc:
            results.append({
                "symbol": coin,
                "status": "error",
                "error": type(exc).__name__,
                "message": str(exc)[:240],
            })
    return {
        "source": "Hyperliquid public Info API",
        "timeframes": list(ALLOWED_TIMEFRAMES),
        "results": results,
        "research_only": True,
        "live_orders": False,
        "orders_submitted": 0,
        "journals_written": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run Project60 brains on live, read-only Hyperliquid market data"
    )
    parser.add_argument("--symbols", default="BTC,ETH,SOL,XRP,DOGE")
    parser.add_argument("--bars", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--cycles", type=int, default=1,
                        help="1 for a single live check; 0 to keep monitoring")
    args = parser.parse_args()
    if args.interval < 30:
        parser.error("--interval must be at least 30 seconds")
    if args.cycles < 0:
        parser.error("--cycles cannot be negative")
    if not 60 <= args.bars <= 1000:
        parser.error("--bars must be between 60 and 1000")
    coins = tuple(dict.fromkeys(
        part.strip().upper() for part in args.symbols.split(",") if part.strip()
    ))
    if not coins:
        parser.error("at least one symbol is required")

    cycle = 0
    while args.cycles == 0 or cycle < args.cycles:
        cycle += 1
        result = run_once(coins, bars=args.bars, timeout=args.timeout)
        result["cycle"] = cycle
        print("HYPERLIQUID_LIVE_BRAIN=" + json.dumps(
            result, ensure_ascii=False, separators=(",", ":")
        ), flush=True)
        if args.cycles == 0 or cycle < args.cycles:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
