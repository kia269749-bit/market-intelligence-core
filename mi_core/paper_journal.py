"""Append-only shadow journal and lightweight outcome resolution."""
from __future__ import annotations
import json
import time
from pathlib import Path
from .order_flow_journal import attach_order_flow

def append_signal(path: str, signal: dict) -> bool:
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    signal_id=signal.get("signal_id")
    if signal_id and p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    row=json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("status")=="OPEN" and row.get("signal_id")==signal_id:
                    return False
        except OSError:
            return False
    record={"ts":int(time.time()),"status":"OPEN",**signal}
    if isinstance(signal.get("order_flow"), dict):
        record=attach_order_flow(record, signal["order_flow"])
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False)+"\n")
    return True

def resolve_signal(entry_price: float, current_price: float, direction: str,
                   stop: float, target: float) -> str:
    d=str(direction).upper()
    if d=="BULLISH":
        if current_price <= stop: return "STOP"
        if current_price >= target: return "TARGET"
    elif d=="BEARISH":
        if current_price >= stop: return "STOP"
        if current_price <= target: return "TARGET"
    return "OPEN"

def resolve_open_signals(path: str, current_price: float | dict, now: int | None = None) -> int:
    """Resolve OPEN records with one price or an asset->price map.

    When a mapping is supplied, each open signal is resolved only against the
    current price for its own asset. This prevents BTC prices from resolving
    ETH or other asset shadow records.
    """
    p=Path(path)
    if not p.exists(): return 0
    try: rows=[json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError): return 0
    changed=0; now=int(time.time() if now is None else now)
    price_map={str(k).upper():float(v) for k,v in current_price.items()} if isinstance(current_price,dict) else None
    for row in rows:
        if row.get("status") != "OPEN": continue
        try:
            if price_map is not None:
                asset=str(row.get("asset","")).upper()
                if asset not in price_map: continue
                price=float(price_map[asset])
            else:
                price=float(current_price)
            status=resolve_signal(float(row["entry_price"]), price,
                                  row["direction"], float(row["stop"]), float(row["target"]))
        except (KeyError, TypeError, ValueError):
            continue
        if status=="OPEN": continue
        entry=float(row["entry_price"]); direction=str(row["direction"]).upper()
        gross_pct=((price-entry)/entry*100) if direction=="BULLISH" else ((entry-price)/entry*100)
        cost_pct=float(row.get("round_trip_cost_pct",0.0) or 0.0)
        capital=float(row.get("capital_usd",500.0) or 500.0)
        row.update({"status":status,"resolved_ts":now,"exit_price":price,
                    "gross_move_pct":round(gross_pct,6),
                    "net_profit_usd":round(capital*(gross_pct-cost_pct)/100,4)})
        changed+=1
    if changed:
        tmp=p.with_suffix(p.suffix+".tmp")
        tmp.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),encoding="utf-8")
        tmp.replace(p)
    return changed

def _bucket_confidence(value):
    try:
        x=float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if x < 0.60:
        return "LOW"
    if x < 0.75:
        return "MEDIUM"
    if x < 0.90:
        return "HIGH"
    return "VERY_HIGH"


def _bucket_economic(value):
    try:
        x=float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if x >= 10.0:
        return "PREFERRED"
    if x >= 4.0:
        return "ACCEPTABLE"
    return "BELOW_MIN"


def _group_outcomes(rows, key_fn):
    groups={}
    for row in rows:
        key=key_fn(row)
        item=groups.setdefault(key, {"resolved":0,"wins":0,"losses":0,"net_profit_usd":0.0})
        item["resolved"] += 1
        if row.get("status") == "TARGET":
            item["wins"] += 1
        elif row.get("status") == "STOP":
            item["losses"] += 1
        item["net_profit_usd"] += float(row.get("net_profit_usd",0.0) or 0.0)
    for item in groups.values():
        n=item["resolved"]
        item["win_rate"]=round(item["wins"]/n,4) if n else 0.0
        item["net_profit_usd"]=round(item["net_profit_usd"],4)
    return groups


def summarize(path: str) -> dict:
    p=Path(path)
    if not p.exists():
        return {
            "count":0,"open":0,"resolved":0,"wins":0,"losses":0,
            "win_rate":0.0,"net_profit_usd":0.0,
            "by_regime":{},"by_direction":{},
            "by_confidence":{},"by_economic_tier":{}
        }

    rows=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    resolved=[r for r in rows if r.get("status") in ("TARGET","STOP")]
    wins=sum(r.get("status")=="TARGET" for r in resolved)
    losses=sum(r.get("status")=="STOP" for r in resolved)
    net=sum(float(r.get("net_profit_usd",0.0) or 0.0) for r in resolved)

    return {
        "count":len(rows),
        "open":sum(r.get("status")=="OPEN" for r in rows),
        "resolved":len(resolved),
        "wins":wins,
        "losses":losses,
        "win_rate":round(wins/len(resolved),4) if resolved else 0.0,
        "net_profit_usd":round(net,4),
        "by_regime":_group_outcomes(
            resolved, lambda r: str(r.get("regime","UNKNOWN")).upper() or "UNKNOWN"
        ),
        "by_direction":_group_outcomes(
            resolved, lambda r: str(r.get("direction","UNKNOWN")).upper() or "UNKNOWN"
        ),
        "by_confidence":_group_outcomes(
            resolved, lambda r: _bucket_confidence(r.get("confidence"))
        ),
        "by_economic_tier":_group_outcomes(
            resolved, lambda r: _bucket_economic(
                r.get("modeled_profit_usd")
            )
        ),
    }
