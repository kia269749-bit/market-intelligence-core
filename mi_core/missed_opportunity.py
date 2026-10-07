"""Lightweight missed-opportunity shadow evaluation.

Records research-only opportunities rejected by the live economic/actionability
gates and later measures what the market actually did over 5/10/20/50 bars.
No orders are placed and no gate is weakened.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

HORIZONS = (5, 10, 20, 50)


def _read(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        return []
    return rows


def _write(path: str, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    tmp.replace(p)


def _latest_prices(project60_file: str, max_rows: int = 200) -> list[dict]:
    p = Path(project60_file)
    if not p.exists():
        return []
    try:
        raw = p.read_text(encoding="utf-8").splitlines()[-max_rows:]
    except OSError:
        return []
    out = []
    for line in raw:
        try:
            x = json.loads(line)
            coins = x.get("coins", {})
            if isinstance(coins, list):
                coins = {
                    str(v.get("coin")): v
                    for v in coins
                    if isinstance(v, dict) and v.get("coin")
                }
            prices = {}
            for asset, row in (coins or {}).items():
                if isinstance(row, dict) and row.get("price") is not None:
                    try:
                        price = float(row["price"])
                        if price > 0:
                            prices[str(asset).upper()] = price
                    except (TypeError, ValueError):
                        pass
            if prices:
                out.append({"ts": int(float(x.get("timestamp", 0))), "prices": prices})
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return out


def append_rejected(path: str, snapshot: dict, project60_file: str) -> bool:
    """Record a rejected directional setup once per timestamp/asset/direction."""
    forecast = (snapshot.get("evidence") or {}).get("forecast") or {}
    if not forecast.get("available"):
        return False
    selected = forecast.get("selected") or {}
    direction = str(selected.get("direction", "")).upper()
    if direction not in ("UP", "DOWN"):
        return False

    economics = snapshot.get("capital_economics") or {}
    combined = (snapshot.get("evidence") or {}).get("combined") or {}
    quality = (snapshot.get("evidence") or {}).get("data_quality") or {}
    asset = str(forecast.get("asset") or "BTC").upper()

    prices = _latest_prices(project60_file, max_rows=3)
    if not prices:
        return False
    entry = prices[-1]["prices"].get(asset)
    if not entry:
        return False
    ts = prices[-1]["ts"]
    if not ts:
        ts = int(time.time())

    rows = _read(path)
    for row in rows:
        if (
            row.get("status") == "OPEN"
            and int(row.get("ts", -1)) == ts
            and str(row.get("asset", "")).upper() == asset
            and str(row.get("direction", "")).upper() == direction
        ):
            return False

    # Only rejected opportunities belong here. This keeps the dataset useful
    # for calibration instead of duplicating accepted paper trades.
    if combined.get("actionable") and economics.get("approved"):
        return False

    horizons = forecast.get("horizons") or []
    record = {
        "ts": ts,
        "status": "OPEN",
        "asset": asset,
        "direction": direction,
        "entry_price": float(entry),
        "bias": combined.get("bias"),
        "confidence": combined.get("confidence"),
        "agreement": combined.get("agreement"),
        "quality": quality.get("status"),
        "regime": forecast.get("regime"),
        "economic_tier": economics.get("tier"),
        "economic_reason": economics.get("reason"),
        "modeled_profit_usd": economics.get("modeled_profit_usd"),
        "expected_move_pct": economics.get("expected_move_pct"),
        "horizons": horizons,
        "research_only": True,
        "live_orders": False,
    }
    rows.append(record)
    _write(path, rows)
    return True


def resolve(path: str, project60_file: str) -> int:
    """Resolve observations once 5/10/20/50 Project60 bars have elapsed."""
    rows = _read(path)
    series = _latest_prices(project60_file, max_rows=300)
    if not rows or not series:
        return 0

    changed = 0
    for row in rows:
        if row.get("status") != "OPEN":
            continue
        try:
            entry_ts = int(row["ts"])
            entry = float(row["entry_price"])
            direction = str(row["direction"]).upper()
            asset = str(row["asset"]).upper()
        except (KeyError, TypeError, ValueError):
            continue

        future = [s for s in series if int(s["ts"]) > entry_ts and asset in s["prices"]]
        if not future:
            continue

        # Project60 is normally one snapshot/minute. Timestamp-based indexing
        # is used rather than wall-clock assumptions, making sparse data safe.
        outcomes = {}
        for h in HORIZONS:
            if len(future) < h:
                continue
            price = float(future[h - 1]["prices"][asset])
            move = ((price - entry) / entry * 100.0)
            directional_move = move if direction == "UP" else -move
            outcomes[str(h)] = {
                "price": round(price, 8),
                "move_pct": round(move, 6),
                "directional_move_pct": round(directional_move, 6),
                "hit_1pct": bool(directional_move >= 1.0),
                "hit_2pct": bool(directional_move >= 2.0),
            }

        if outcomes:
            row["outcomes"] = outcomes
            row["resolved_bars"] = max(int(k) for k in outcomes)
            if row["resolved_bars"] >= 50:
                row["status"] = "RESOLVED"
            changed += 1

    if changed:
        _write(path, rows)
    return changed


def summarize(path: str) -> dict:
    rows = _read(path)
    resolved = [r for r in rows if r.get("outcomes")]
    by_reason = {}
    by_tier = {}
    for row in resolved:
        reason = str(row.get("economic_reason") or "unknown")
        tier = str(row.get("economic_tier") or "unknown")
        for bucket, key in ((by_reason, reason), (by_tier, tier)):
            item = bucket.setdefault(key, {"count": 0, "positive_5": 0, "positive_20": 0, "positive_50": 0})
            item["count"] += 1
        for h in ("5", "20", "50"):
            vals = [r for r in resolved if h in (r.get("outcomes") or {})]
            if not vals:
                continue
            positive = sum(float(r["outcomes"][h].get("directional_move_pct", 0)) > 0 for r in vals)
            key = "positive_" + h
            # Aggregate below at report level.
    def stats(h):
        vals = [
            r["outcomes"][h]["directional_move_pct"]
            for r in resolved
            if h in (r.get("outcomes") or {})
        ]
        if not vals:
            return {"count": 0, "positive_rate": 0.0, "avg_directional_move_pct": 0.0, "best_move_pct": 0.0}
        return {
            "count": len(vals),
            "positive_rate": round(sum(v > 0 for v in vals) / len(vals), 4),
            "avg_directional_move_pct": round(sum(vals) / len(vals), 6),
            "best_move_pct": round(max(vals), 6),
        }
    return {
        "count": len(rows),
        "open": sum(r.get("status") == "OPEN" for r in rows),
        "resolved": sum(r.get("status") == "RESOLVED" for r in rows),
        "horizons": {str(h): stats(str(h)) for h in HORIZONS},
        "by_economic_reason": by_reason,
        "by_economic_tier": by_tier,
        "research_only": True,
        "live_orders": False,
    }
