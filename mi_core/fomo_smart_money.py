from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TraderFill:
    trader_id: str
    token: str
    side: str
    timestamp: int
    price_usd: float
    amount_usd: float


@dataclass(frozen=True)
class TrackedPosition:
    trader_id: str
    token: str
    entry_price_usd: float
    size_usd: float
    opened_at: int
    last_price_usd: float
    unrealized_return_pct: float
    age_seconds: int


@dataclass(frozen=True)
class TraderAction:
    trader_id: str
    token: str
    action: str
    timestamp: int
    price_usd: float
    amount_usd: float


def build_open_positions(
    fills: Sequence[TraderFill],
    *,
    as_of: int,
) -> list[TrackedPosition]:
    books: dict[tuple[str, str], dict[str, float | int]] = {}
    for fill in sorted(fills, key=lambda x: x.timestamp):
        if fill.price_usd <= 0 or fill.amount_usd <= 0:
            continue
        key = (fill.trader_id, fill.token)
        book = books.setdefault(key, {
            "quantity": 0.0,
            "cost_usd": 0.0,
            "opened_at": fill.timestamp,
            "last_price": fill.price_usd,
        })
        quantity = fill.quantity if fill.quantity is not None else fill.amount_usd / fill.price_usd
        if quantity <= 0:
            continue
        if fill.side.lower() == "buy":
            book["quantity"] = float(book["quantity"]) + quantity
            book["cost_usd"] = float(book["cost_usd"]) + quantity * fill.price_usd
            if float(book["quantity"]) == quantity:
                book["opened_at"] = fill.timestamp
        elif fill.side.lower() == "sell":
            current_qty = float(book["quantity"])
            sold_qty = min(current_qty, quantity)
            entry_price = float(book["cost_usd"]) / current_qty if current_qty else 0.0
            remaining = max(0.0, current_qty - sold_qty)
            book["quantity"] = remaining
            book["cost_usd"] = entry_price * remaining
            if remaining == 0.0:
                book["cost_usd"] = 0.0
        book["last_price"] = fill.price_usd

    output: list[TrackedPosition] = []
    for (trader_id, token), book in books.items():
        quantity = float(book["quantity"])
        if quantity <= 0:
            continue
        cost = float(book["cost_usd"])
        entry = cost / quantity if quantity else 0.0
        last = float(book["last_price"])
        size = quantity * last
        ret = (last / entry - 1.0) * 100.0 if entry > 0 else 0.0
        opened = int(book["opened_at"])
        output.append(TrackedPosition(
            trader_id=trader_id,
            token=token,
            entry_price_usd=round(entry, 10),
            size_usd=round(size, 2),
            opened_at=opened,
            last_price_usd=round(last, 10),
            unrealized_return_pct=round(ret, 6),
            age_seconds=max(0, int(as_of) - opened),
            quantity=round(quantity, 10),
        ))
    return output


def detect_trader_actions(
    fills: Iterable[TraderFill],
    *,
    min_buy_usd: float = 0.0,
    min_sell_usd: float = 0.0,
) -> list[TraderAction]:
    output: list[TraderAction] = []
    for fill in sorted(fills, key=lambda x: x.timestamp):
        side = fill.side.lower()
        if side == "buy" and fill.amount_usd >= min_buy_usd:
            action = "BUY"
        elif side == "sell" and fill.amount_usd >= min_sell_usd:
            action = "SELL"
        else:
            continue
        output.append(TraderAction(
            trader_id=fill.trader_id,
            token=fill.token,
            action=action,
            timestamp=fill.timestamp,
            price_usd=fill.price_usd,
            amount_usd=fill.amount_usd,
        ))
    return output
