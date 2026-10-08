"""Research-only adapter that turns Project60 trade-flow evidence into a bounded flow score.

This layer is deliberately not a trade trigger. It exposes a consistent feature
for logging and later OOS ablation, while preserving every base signal.
"""
from __future__ import annotations


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_order_flow_evidence(project60=None, market_bias="NEUTRAL"):
    assets = (project60 or {}).get("assets") or {}
    usable = []
    for name, asset in assets.items():
        if not isinstance(asset, dict) or not asset.get("available"):
            continue
        imbalance = _num(asset.get("trade_imbalance_pct"))
        usable.append((str(name).upper(), max(-1.0, min(1.0, imbalance / 100.0))))

    if not usable:
        return {
            "available": False,
            "score": 0.0,
            "direction": "NEUTRAL",
            "agreement": 0.0,
            "assets": 0,
            "research_only": True,
            "live_orders": False,
        }

    score = sum(v for _, v in usable) / len(usable)
    direction = "BULLISH" if score > 0.20 else "BEARISH" if score < -0.20 else "NEUTRAL"
    directional = str(market_bias).upper()
    agreement = abs(score) if directional == direction else 0.0
    if direction == "NEUTRAL":
        agreement = 0.0

    return {
        "available": True,
        "score": round(score, 6),
        "direction": direction,
        "agreement": round(min(1.0, agreement), 6),
        "assets": len(usable),
        "asset_scores": {name: round(value, 6) for name, value in usable},
        "used_as_vote": False,
        "research_only": True,
        "live_orders": False,
    }
