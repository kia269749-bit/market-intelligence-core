"""Project60 normalized order-book and executed-trade flow specialists."""
from __future__ import annotations

from collections.abc import Mapping
from .contracts import BrainProposal, MarketSnapshot


def evaluate_project60_flow(snapshot: MarketSnapshot) -> list[BrainProposal]:
    assets = snapshot.payload.get("project60_assets")
    ts = snapshot.payload.get("project60_timestamp_ms")
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        ts = None
    if not isinstance(assets, Mapping):
        assets = {}
    symbol = str(snapshot.symbol).upper()
    base = symbol
    for suffix in ("USDT", "USDC", "USD", "PERP"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break
    asset = assets.get(base) or assets.get(symbol) or {}
    if not isinstance(asset, Mapping):
        asset = {}
    age_ok = ts is not None and ts <= snapshot.as_of_ms and snapshot.as_of_ms - ts <= 180_000
    specs = (
        ("market.project60_orderbook_imbalance", "orderbook_imbalance_pct", 10.0,
         "Project60:orderbook_imbalance", "orderbook"),
        ("market.project60_trade_flow", "trade_imbalance_pct", 20.0,
         "Project60:trade_imbalance", "trades"),
    )
    results = []
    for brain_id, field, threshold, source, label in specs:
        try:
            value = float(asset[field])
        except (KeyError, TypeError, ValueError):
            value = None
        if not asset.get("available") or not age_ok or value is None:
            reason = "project60_snapshot_missing_stale_or_field_unavailable"
            results.append(BrainProposal(
                brain_id=brain_id, family="orderflow", direction="NO_TRADE",
                confidence=0.0, as_of_ms=snapshot.as_of_ms,
                source_ids=(source,), reasons=(reason,), available=False,
            ))
            continue
        direction = "LONG" if value >= threshold else "SHORT" if value <= -threshold else "NO_TRADE"
        confidence = min(0.90, abs(value) / (threshold * 4.0)) if direction != "NO_TRADE" else 0.0
        results.append(BrainProposal(
            brain_id=brain_id, family="orderflow", direction=direction,
            confidence=round(confidence, 4), as_of_ms=snapshot.as_of_ms,
            source_ids=(source,), reasons=(f"{label}_imbalance_pct:{value:.4f}",),
        ))
    return results
