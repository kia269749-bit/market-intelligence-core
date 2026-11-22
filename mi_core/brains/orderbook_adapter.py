"""Order-book imbalance and microprice specialist using normalized L2 snapshots."""
from __future__ import annotations

from collections.abc import Mapping
from .contracts import BrainProposal, MarketSnapshot


def evaluate_orderbook_specialist(snapshot: MarketSnapshot, levels: int = 10,
                                  min_imbalance: float = 0.12,
                                  max_age_ms: int = 60_000) -> BrainProposal:
    book = snapshot.payload.get("orderbook")
    if not isinstance(book, Mapping):
        return _unavailable(snapshot, "orderbook_feed_unavailable")
    try:
        ts = int(book["timestamp_ms"])
        bids = book["bids"][:levels]
        asks = book["asks"][:levels]
        bid_size = sum(float(level[1]) for level in bids)
        ask_size = sum(float(level[1]) for level in asks)
        best_bid, best_ask = float(bids[0][0]), float(asks[0][0])
    except (KeyError, TypeError, ValueError, IndexError):
        return _unavailable(snapshot, "invalid_orderbook_schema")
    if ts > snapshot.as_of_ms or snapshot.as_of_ms - ts > max_age_ms:
        return _unavailable(snapshot, "stale_or_future_orderbook")
    if bid_size <= 0 or ask_size <= 0 or best_bid <= 0 or best_ask <= best_bid:
        return _unavailable(snapshot, "invalid_orderbook_depth_or_spread")

    imbalance = (bid_size - ask_size) / (bid_size + ask_size)
    mid = (best_bid + best_ask) / 2.0
    microprice = (best_ask * bid_size + best_bid * ask_size) / (bid_size + ask_size)
    microprice_edge = (microprice - mid) / mid
    if imbalance >= min_imbalance and microprice_edge > 0:
        direction = "LONG"
    elif imbalance <= -min_imbalance and microprice_edge < 0:
        direction = "SHORT"
    else:
        direction = "NO_TRADE"
    confidence = min(0.95, abs(imbalance) * 1.5 + abs(microprice_edge) * 500.0)
    return BrainProposal(
        brain_id="market.orderbook_imbalance",
        family="orderflow",
        direction=direction,
        confidence=round(confidence, 4) if direction != "NO_TRADE" else 0.0,
        as_of_ms=snapshot.as_of_ms,
        source_ids=("Project60:orderbook_L2", "feature:OBI", "feature:microprice"),
        reasons=(f"depth_imbalance:{imbalance:.6f}", f"microprice_edge:{microprice_edge:.8f}"),
    )


def _unavailable(snapshot: MarketSnapshot, reason: str) -> BrainProposal:
    return BrainProposal(
        brain_id="market.orderbook_imbalance",
        family="orderflow",
        direction="NO_TRADE",
        confidence=0.0,
        as_of_ms=snapshot.as_of_ms,
        source_ids=("Project60:orderbook_L2",),
        reasons=(reason,),
        available=False,
    )
