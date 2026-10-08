"""Lightweight market-microstructure features for research/backtesting.

No live-order logic. All functions are deterministic and operate on public
order-book/trade snapshots so the layer can be validated before integration.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence


def _levels(levels: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
    out = []
    for level in levels or []:
        if len(level) < 2:
            continue
        try:
            price, qty = float(level[0]), float(level[1])
        except (TypeError, ValueError):
            continue
        if price > 0 and qty > 0 and math.isfinite(price) and math.isfinite(qty):
            out.append((price, qty))
    return out


def _weighted_depth(levels: list[tuple[float, float]], decay: float) -> float:
    total = 0.0
    for i, (_, qty) in enumerate(levels):
        total += qty * (decay ** i)
    return total


def order_book_features(
    bids: Iterable[Sequence[float]],
    asks: Iterable[Sequence[float]],
    levels: int = 10,
    decay: float = 0.85,
) -> dict:
    """Return normalized L2 features from one order-book snapshot."""
    if levels < 1:
        raise ValueError("levels must be >= 1")
    if not 0 < decay <= 1:
        raise ValueError("decay must be in (0, 1]")

    bid = sorted(_levels(bids), key=lambda x: x[0], reverse=True)[:levels]
    ask = sorted(_levels(asks), key=lambda x: x[0])[:levels]
    if not bid or not ask:
        return {"valid": False, "reason": "missing_side"}

    best_bid, bid_qty = bid[0]
    best_ask, ask_qty = ask[0]
    mid = (best_bid + best_ask) / 2.0
    spread = best_ask - best_bid
    spread_bps = spread / mid * 10000.0 if mid else None

    bid_depth = _weighted_depth(bid, decay)
    ask_depth = _weighted_depth(ask, decay)
    depth_total = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / depth_total if depth_total else 0.0

    microprice = (
        (best_ask * bid_qty + best_bid * ask_qty) / (bid_qty + ask_qty)
        if (bid_qty + ask_qty)
        else mid
    )
    micro_edge_bps = (microprice - mid) / mid * 10000.0 if mid else 0.0

    return {
        "valid": True,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread_bps": spread_bps,
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "depth_imbalance": imbalance,
        "microprice": microprice,
        "microprice_edge_bps": micro_edge_bps,
        "bid_levels": len(bid),
        "ask_levels": len(ask),
    }


def trade_flow_features(trades: Iterable[Mapping], price_key: str = "price", qty_key: str = "qty") -> dict:
    """Aggregate signed trade flow. side may be buy/sell or is_buyer_maker."""
    buy = sell = 0.0
    buy_count = sell_count = 0
    for t in trades or []:
        try:
            qty = float(t.get(qty_key, 0.0))
        except (TypeError, ValueError):
            continue
        if qty <= 0 or not math.isfinite(qty):
            continue
        side = str(t.get("side", "")).lower()
        if side == "buy":
            buy += qty
            buy_count += 1
        elif side == "sell":
            sell += qty
            sell_count += 1
        elif "is_buyer_maker" in t:
            if bool(t.get("is_buyer_maker")):
                sell += qty
                sell_count += 1
            else:
                buy += qty
                buy_count += 1
    total = buy + sell
    return {
        "buy_qty": buy,
        "sell_qty": sell,
        "total_qty": total,
        "trade_imbalance": (buy - sell) / total if total else 0.0,
        "buy_count": buy_count,
        "sell_count": sell_count,
    }


def flow_confluence(book: Mapping, trades: Mapping) -> dict:
    """Combine book and executed-flow evidence without producing a trade order."""
    if not book.get("valid"):
        return {"score": 0.0, "direction": "NEUTRAL", "quality": "INVALID"}

    b = float(book.get("depth_imbalance", 0.0))
    t = float(trades.get("trade_imbalance", 0.0))
    m = float(book.get("microprice_edge_bps", 0.0))
    # Bounded evidence score. Trade flow gets the largest weight because it
    # represents executed demand rather than resting intent.
    score = max(-1.0, min(1.0, 0.40 * b + 0.45 * t + 0.15 * math.tanh(m / 2.0)))
    direction = "BULLISH" if score >= 0.20 else "BEARISH" if score <= -0.20 else "NEUTRAL"
    return {
        "score": score,
        "direction": direction,
        "quality": "CONFIRMED" if abs(b) >= 0.15 and abs(t) >= 0.15 and b * t > 0 else "MIXED",
    }
