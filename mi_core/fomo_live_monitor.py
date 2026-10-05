from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

@dataclass(frozen=True)
class LiveFomoEvent:
    event_id: str
    trader_id: str
    trader_handle: str
    token: str
    token_address: str
    chain: str
    action: str
    usd_value: float
    timestamp_ms: int
    trade_id: str | None = None

def parse_alert(payload: Mapping[str, Any]) -> LiveFomoEvent | None:
    if payload.get("type") != "alert":
        return None
    action = str(payload.get("alertType", "")).lower()
    if action not in {"buy", "sell"}:
        return None
    event_id = str(payload.get("eventId", "")).strip()
    trader_id = str(payload.get("userId", "")).strip()
    if not event_id or not trader_id:
        return None
    return LiveFomoEvent(event_id, trader_id, str(payload.get("trader", "")),
        str(payload.get("token", "")), str(payload.get("tokenAddress", "")),
        str(payload.get("chain", "")), action.upper(),
        float(payload.get("usdValue") or 0.0), int(payload.get("ts") or 0),
        str(payload.get("tradeId")) if payload.get("tradeId") else None)

def dedupe_events(events: Sequence[LiveFomoEvent]) -> list[LiveFomoEvent]:
    seen: set[str] = set()
    out: list[LiveFomoEvent] = []
    for event in events:
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        out.append(event)
    return out
