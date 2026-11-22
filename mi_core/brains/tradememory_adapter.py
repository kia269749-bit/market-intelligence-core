"""Build a TradeMemory record_decision request from a Project60 candidate.

This is an offline payload builder only. It does not call the TradeMemory
server, create a real trade, or convert Project60 fixed-horizon labels into
realized account-currency PnL. TradeMemory requires an explicit lot_size;
Project60 does not infer one for a research signal.
"""
from __future__ import annotations
from collections.abc import Mapping
import math


def signal_to_tradememory_decision(
    signal: Mapping,
    *,
    trade_id: str,
    lot_size: float,
    session: str | None = None,
) -> dict:
    """Return the documented TradeMemory POST /trade/record_decision body."""
    if not isinstance(trade_id, str) or not trade_id.startswith("T-"):
        raise ValueError("trade_id must be an explicit T-... identifier")
    try:
        size = float(lot_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("lot_size must be explicitly supplied") from exc
    if not math.isfinite(size) or size <= 0:
        raise ValueError("lot_size must be finite and positive")
    direction = str(signal.get("direction", "")).lower()
    if direction not in ("long", "short"):
        raise ValueError("only directional Project60 signals can be mapped")
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
    reasoning = "; ".join(str(item) for item in reasons) or "Project60 research candidate"
    market_context = {"price": price}
    if session is not None:
        if not isinstance(session, str) or not session.strip():
            raise ValueError("session must be a non-empty string when supplied")
        market_context["session"] = session.strip().lower()
    if signal.get("regime"):
        market_context["indicators"] = {"regime": str(signal["regime"])}
    # TradeMemory assigns its own timestamp. No outcome/PnL is fabricated.
    return {
        "trade_id": trade_id, "symbol": symbol, "direction": direction,
        "lot_size": size, "strategy": strategy, "confidence": confidence,
        "reasoning": reasoning, "market_context": market_context, "references": [],
    }
