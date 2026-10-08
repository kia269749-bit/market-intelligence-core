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
def liquidity_event_features(
    previous: Mapping,
    current: Mapping,
    trades: Mapping,
    price_change_bps: float | None = None,
) -> dict:
    """Detect simple absorption/vacuum states from consecutive L2 snapshots.

    These are evidence features only. They do not emit orders.
    """
    if not previous.get("valid") or not current.get("valid"):
        return {"valid": False, "state": "UNKNOWN"}

    bid_prev = max(float(previous.get("bid_depth", 0.0)), 0.0)
    ask_prev = max(float(previous.get("ask_depth", 0.0)), 0.0)
    bid_now = max(float(current.get("bid_depth", 0.0)), 0.0)
    ask_now = max(float(current.get("ask_depth", 0.0)), 0.0)

    def pct_change(now: float, old: float) -> float:
        return (now - old) / old if old > 0 else 0.0

    bid_delta = pct_change(bid_now, bid_prev)
    ask_delta = pct_change(ask_now, ask_prev)
    flow = float(trades.get("trade_imbalance", 0.0))
    move = float(price_change_bps or 0.0)

    # Large aggressive flow with little price movement is a useful absorption
    # candidate, not proof of hidden liquidity.
    buy_absorption = flow >= 0.45 and abs(move) <= 3.0 and bid_now > 0
    sell_absorption = flow <= -0.45 and abs(move) <= 3.0 and ask_now > 0

    # A sharp loss of displayed depth is a liquidity-vacuum candidate.
    bid_vacuum = bid_delta <= -0.35
    ask_vacuum = ask_delta <= -0.35

    if buy_absorption:
        state = "BUY_ABSORPTION"
    elif sell_absorption:
        state = "SELL_ABSORPTION"
    elif bid_vacuum and ask_vacuum:
        state = "TWO_SIDED_VACUUM"
    elif bid_vacuum:
        state = "BID_VACUUM"
    elif ask_vacuum:
        state = "ASK_VACUUM"
    else:
        state = "NORMAL"

    return {
        "valid": True,
        "state": state,
        "bid_depth_change": bid_delta,
        "ask_depth_change": ask_delta,
        "price_change_bps": move,
        "trade_imbalance": flow,
    }


def flow_regime_features(book: Mapping, trades: Mapping, price_change_bps: float) -> dict:
    """Classify flow as trend/absorption/conflict/liquidity-neutral evidence."""
    if not book.get("valid"):
        return {"regime": "UNKNOWN"}

    b = float(book.get("depth_imbalance", 0.0))
    t = float(trades.get("trade_imbalance", 0.0))
    p = float(price_change_bps)

    # Opposing displayed depth and executed flow is a conflict even when
    # price has not moved far enough to qualify as a trend.
    if b * t < 0 and abs(b) >= 0.20 and abs(t) >= 0.20:
        return {"regime": "FLOW_CONFLICT"}
    if abs(t) >= 0.45 and abs(p) <= 3.0:
        return {"regime": "ABSORPTION_CANDIDATE"}
    if abs(b) >= 0.25 and abs(t) >= 0.25 and b * t > 0 and abs(p) >= 3.0:
        return {"regime": "FLOW_TREND"}
    return {"regime": "NEUTRAL_FLOW"}


def sweep_features(
    book: Mapping,
    trades: Iterable[Mapping],
    min_levels: int = 2,
) -> dict:
    """Detect an executed sweep proxy across multiple displayed price levels.

    This is deliberately conservative: without a full event stream it cannot
    prove that one actor swept the book. It only detects trades spanning
    multiple current displayed levels.
    """
    if not book.get("valid"):
        return {"valid": False, "state": "UNKNOWN"}

    if min_levels < 2:
        raise ValueError("min_levels must be >= 2")

    best_bid = float(book.get("best_bid", 0.0))
    best_ask = float(book.get("best_ask", 0.0))
    buy_prices = []
    sell_prices = []

    for trade in trades or []:
        try:
            price = float(trade.get("price", 0.0))
            qty = float(trade.get("qty", 0.0))
        except (TypeError, ValueError):
            continue
        if price <= 0 or qty <= 0 or not math.isfinite(price) or not math.isfinite(qty):
            continue
        side = str(trade.get("side", "")).lower()
        if not side and "is_buyer_maker" in trade:
            side = "sell" if bool(trade.get("is_buyer_maker")) else "buy"
        if side == "buy" and price >= best_ask:
            buy_prices.append(price)
        elif side == "sell" and price <= best_bid:
            sell_prices.append(price)

    buy_levels = len(set(buy_prices))
    sell_levels = len(set(sell_prices))
    if buy_levels >= min_levels and buy_levels > sell_levels:
        state = "BUY_SWEEP_CANDIDATE"
    elif sell_levels >= min_levels and sell_levels > buy_levels:
        state = "SELL_SWEEP_CANDIDATE"
    elif buy_levels >= min_levels and sell_levels >= min_levels:
        state = "TWO_SIDED_SWEEP_CANDIDATE"
    else:
        state = "NONE"

    return {
        "valid": True,
        "state": state,
        "buy_levels": buy_levels,
        "sell_levels": sell_levels,
    }


def pull_vacuum_proxy(
    previous: Mapping,
    current: Mapping,
    trades: Mapping,
    threshold: float = 0.35,
) -> dict:
    """Estimate displayed-liquidity pulling without claiming true cancellations.

    A large depth loss with little executed volume is a pulling/vacuum proxy.
    """
    if not previous.get("valid") or not current.get("valid"):
        return {"valid": False, "state": "UNKNOWN"}

    if not 0 < threshold < 1:
        raise ValueError("threshold must be in (0, 1)")

    def change(now: float, old: float) -> float:
        return (now - old) / old if old > 0 else 0.0

    bid_change = change(
        float(current.get("bid_depth", 0.0)),
        float(previous.get("bid_depth", 0.0)),
    )
    ask_change = change(
        float(current.get("ask_depth", 0.0)),
        float(previous.get("ask_depth", 0.0)),
    )
    executed = abs(float(trades.get("trade_imbalance", 0.0)))
    # Imbalance alone is not volume. Keep this proxy conservative when the
    # caller only supplies normalized flow and cannot provide notional volume.
    low_execution_evidence = executed < 0.20

    if low_execution_evidence and bid_change <= -threshold and ask_change > -threshold:
        state = "BID_PULLING_PROXY"
    elif low_execution_evidence and ask_change <= -threshold and bid_change > -threshold:
        state = "ASK_PULLING_PROXY"
    elif low_execution_evidence and bid_change <= -threshold and ask_change <= -threshold:
        state = "TWO_SIDED_PULLING_PROXY"
    else:
        state = "NONE"

    return {
        "valid": True,
        "state": state,
        "bid_depth_change": bid_change,
        "ask_depth_change": ask_change,
        "low_execution_evidence": low_execution_evidence,
    }


def wall_persistence_features(
    snapshots: Sequence[Mapping],
    side: str = "bid",
    wall_multiple: float = 3.0,
) -> dict:
    """Measure persistence of unusually large displayed depth across snapshots.

    The function uses the largest level quantity relative to the median level
    quantity. It is a displayed-liquidity persistence signal, not proof of
    intent, spoofing, or cancellation.
    """
    if side not in {"bid", "ask"}:
        raise ValueError("side must be bid or ask")
    if wall_multiple <= 1:
        raise ValueError("wall_multiple must be > 1")

    hits = 0
    valid = 0
    for snapshot in snapshots or []:
        levels = snapshot.get(f"{side}s") if isinstance(snapshot, Mapping) else None
        clean = _levels(levels or [])
        if not clean:
            continue
        quantities = sorted(qty for _, qty in clean)
        median = quantities[len(quantities) // 2]
        if median <= 0:
            continue
        valid += 1
        if max(quantities) >= median * wall_multiple:
            hits += 1

    persistence = hits / valid if valid else 0.0
    state = "PERSISTENT_WALL" if persistence >= 0.60 and valid >= 3 else "NO_PERSISTENT_WALL"
    return {
        "valid": valid > 0,
        "state": state,
        "valid_snapshots": valid,
        "wall_hits": hits,
        "persistence": persistence,
    }


def flow_price_divergence(
    trade_imbalance: float,
    price_change_bps: float,
    threshold: float = 0.30,
) -> dict:
    """Flag disagreement between executed flow direction and price movement."""
    if threshold <= 0:
        raise ValueError("threshold must be > 0")

    flow = float(trade_imbalance)
    move = float(price_change_bps)
    if abs(flow) < threshold or abs(move) < threshold:
        return {"state": "NONE", "strength": 0.0}

    opposite = (flow > 0 and move < 0) or (flow < 0 and move > 0)
    if not opposite:
        return {"state": "ALIGNED", "strength": min(1.0, abs(flow))}

    strength = min(1.0, abs(flow) * abs(move) / (threshold * max(threshold, 3.0)))
    return {
        "state": "BUY_FLOW_PRICE_DOWN" if flow > 0 else "SELL_FLOW_PRICE_UP",
        "strength": strength,
    }
