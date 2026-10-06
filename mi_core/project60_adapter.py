"""Read-only adapter for Project 60 market.jsonl snapshots.

The adapter is schema-aware for the current Project 60 format and intentionally
does not control, restart, or modify the Project 60 service.
"""
from __future__ import annotations

import json
from pathlib import Path


def _last_jsonl(path: str):
    """Read only the final non-empty JSONL record without scanning the file."""
    p = Path(path)
    if not p.exists():
        return None

    with p.open("rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        buf = b""
        while pos > 0:
            step = min(8192, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
            lines = buf.splitlines()
            if len(lines) > 1:
                for line in reversed(lines[1:]):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        return json.loads(line.decode("utf-8", "ignore"))
                    except json.JSONDecodeError:
                        continue
        for line in reversed(buf.splitlines()):
            line = line.strip()
            if line:
                try:
                    return json.loads(line.decode("utf-8", "ignore"))
                except json.JSONDecodeError:
                    return None
    return None


def _asset_direction(asset):
    """Return direction plus lightweight evidence from order book/trades."""
    if not isinstance(asset, dict) or "error" in asset:
        return "UNKNOWN", 0.0, []

    ob = asset.get("orderbook") or {}
    tr = asset.get("trades") or {}
    ob_imb = ob.get("imbalance_pct")
    tr_imb = tr.get("imbalance_pct")
    evidence = []

    if isinstance(ob_imb, (int, float)):
        if ob_imb >= 10:
            evidence.append("orderbook_buy_pressure")
        elif ob_imb <= -10:
            evidence.append("orderbook_sell_pressure")

    if isinstance(tr_imb, (int, float)):
        if tr_imb >= 20:
            evidence.append("trade_buy_pressure")
        elif tr_imb <= -20:
            evidence.append("trade_sell_pressure")

    votes = sum(1 for x in evidence if "buy" in x), sum(
        1 for x in evidence if "sell" in x
    )
    if votes[0] and votes[1]:
        return "UNKNOWN", 0.0, evidence
    if not votes[0] and not votes[1]:
        return "UNKNOWN", 0.0, evidence

    direction = "BULLISH" if votes[0] else "BEARISH"
    confidence = 0.60 if len(evidence) == 1 else 0.80
    return direction, confidence, evidence


def read_snapshot(path: str):
    raw = _last_jsonl(path)
    if not raw:
        return {"available": False, "reason": "no_snapshot"}

    coins = raw.get("coins") if isinstance(raw, dict) else None
    coins = coins if isinstance(coins, dict) else {}
    assets = {}
    for symbol, asset in coins.items():
        if not isinstance(asset, dict) or "error" in asset:
            assets[str(symbol).upper()] = {
                "available": False,
                "error": asset.get("error") if isinstance(asset, dict) else "invalid",
            }
            continue
        direction, confidence, evidence = _asset_direction(asset)
        assets[str(symbol).upper()] = {
            "available": True,
            "coin": asset.get("coin", symbol),
            "price": asset.get("price"),
            "open_interest": asset.get("open_interest"),
            "funding": asset.get("funding"),
            "orderbook_imbalance_pct": (asset.get("orderbook") or {}).get("imbalance_pct"),
            "trade_imbalance_pct": (asset.get("trades") or {}).get("imbalance_pct"),
            "buy_usd": (asset.get("trades") or {}).get("buy_usd"),
            "sell_usd": (asset.get("trades") or {}).get("sell_usd"),
            "direction": direction,
            "confidence": confidence,
            "evidence": evidence,
        }

    return {
        "available": True,
        "timestamp": raw.get("timestamp"),
        "datetime": raw.get("datetime"),
        "source": raw.get("source"),
        "assets": assets,
    }


def summarize(path: str):
    data = read_snapshot(path)
    if not data.get("available"):
        return data

    usable = [
        v for v in data["assets"].values()
        if v.get("available") and v.get("direction") in ("BULLISH", "BEARISH")
    ]
    bullish = sum(v["direction"] == "BULLISH" for v in usable)
    bearish = sum(v["direction"] == "BEARISH" for v in usable)

    if bullish and bearish:
        bias, confidence = "NEUTRAL", 0.50
    elif bullish:
        bias = "BULLISH"
        confidence = sum(v["confidence"] for v in usable if v["direction"] == "BULLISH") / bullish
    elif bearish:
        bias = "BEARISH"
        confidence = sum(v["confidence"] for v in usable if v["direction"] == "BEARISH") / bearish
    else:
        bias, confidence = "UNKNOWN", 0.0

    return {
        "available": True,
        "timestamp": data.get("timestamp"),
        "datetime": data.get("datetime"),
        "source": data.get("source"),
        "assets": data["assets"],
        "bias": bias,
        "confidence": round(min(1.0, confidence), 4),
    }


def live_evidence(path: str):
    data = summarize(path)
    if not data.get("available"):
        return {"available": False, "bias": "UNKNOWN", "confidence": 0.0, "assets": {}}
    return {
        "available": True,
        "bias": data.get("bias", "UNKNOWN"),
        "confidence": data.get("confidence", 0.0),
        "assets": data.get("assets", {}),
        "timestamp": data.get("timestamp") or data.get("datetime"),
    }
