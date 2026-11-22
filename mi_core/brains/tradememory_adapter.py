"""Strict, offline mapping from Project60 journals to TradeMemory records.

This module does not call TradeMemory, create orders, or infer execution fields.
Callers must explicitly provide TradeMemory's required lot_size and session.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping


def _utc_iso(milliseconds: Any, field: str) -> str:
    try:
        value = int(milliseconds)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be epoch milliseconds") from exc
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def signal_to_tradememory(
    signal: Mapping[str, Any],
    *,
    trade_id: str,
    lot_size: float,
    session: str,
    outcome: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one Project60 signal to TradeMemory's decision payload.

    lot_size and session are mandatory inputs because Project60's research
    signals do not contain position sizing or session attribution. They are
    never fabricated. Outcome PnL is deliberately not synthesized from a
    fixed-horizon percentage return.
    """
    if not isinstance(trade_id, str) or not trade_id.startswith("T-"):
        raise ValueError("trade_id must be an explicit TradeMemory T-... identifier")
    try:
        size = float(lot_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("lot_size must be explicitly supplied") from exc
    if not math.isfinite(size) or size <= 0:
        raise ValueError("lot_size must be finite and positive")
    if not isinstance(session, str) or not session.strip():
        raise ValueError("session must be explicitly supplied")

    direction = str(signal.get("direction", "")).upper()
    if direction not in ("LONG", "SHORT"):
        raise ValueError("only directional Project60 signals can be exported")
    symbol = str(signal.get("symbol", "")).strip().upper()
    strategy = str(signal.get("brain_id", "")).strip()
    if not symbol or not strategy:
        raise ValueError("signal requires symbol and brain_id")
    try:
        confidence = float(signal["confidence"])
        price = float(signal["entry_price"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("signal requires numeric confidence and entry_price") from exc
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be finite and in [0, 1]")
    if not math.isfinite(price) or price <= 0:
        raise ValueError("entry_price must be finite and positive")

    reasons = signal.get("reasons") or []
    reasoning = "; ".join(str(item) for item in reasons) or "Project60 research signal"
    payload: dict[str, Any] = {
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction.lower(),
        "lot_size": size,
        "strategy": strategy,
        "confidence": confidence,
        "reasoning": reasoning,
        "market_context": {"price": price, "session": session.strip().lower()},
        "references": [],
        "timestamp": _utc_iso(signal.get("as_of_ms"), "as_of_ms"),
        "tags": ["project60", "research_only", "no_live_execution"],
    }
    regime = signal.get("regime")
    if regime:
        payload["market_context"]["indicators"] = {"regime": str(regime)}

    if outcome is not None:
        if outcome.get("resolved") is not True:
            raise ValueError("only resolved outcomes can be exported")
        try:
            exit_price = float(outcome["exit_price"])
            net_move = float(outcome["net_move_pct"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("resolved outcome requires exit_price and net_move_pct") from exc
        if not math.isfinite(exit_price) or exit_price <= 0 or not math.isfinite(net_move):
            raise ValueError("outcome values must be finite and exit_price positive")
        payload["exit_price"] = exit_price
        payload["exit_timestamp"] = _utc_iso(outcome.get("resolved_ts_ms"), "resolved_ts_ms")
        payload["lessons"] = (
            "Project60 fixed-horizon research classification; "
            f"net directional move after configured round-trip cost: {net_move:.6f}%. "
            "This is not realized account-currency PnL or an executed trade."
        )
        payload["tags"].append("outcome_win" if outcome.get("won") is True else "outcome_loss")
    return payload
