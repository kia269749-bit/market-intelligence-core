"""Append-only shadow journal and lightweight outcome resolution."""
from __future__ import annotations
import json
import math
import time
from pathlib import Path
from .cost_policy import DEFAULT_COST_POLICY

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
            entry=float(row["entry_price"])
            direction=str(row["direction"]).upper()
            stop=float(row["stop"])
            target=float(row["target"])
            status=resolve_signal(entry, price, direction, stop, target)
        except (KeyError, TypeError, ValueError):
            continue
        if status=="OPEN": continue
        # Cap target fills at the target price. For a stop gap, use the worse
        # observed price so a sparse price poll cannot inflate shadow PnL.
        if status=="TARGET":
            exit_price=target
        elif direction=="BULLISH":
            exit_price=min(price,stop)
        else:
            exit_price=max(price,stop)
        gross_pct=((exit_price-entry)/entry*100) if direction=="BULLISH" else ((entry-exit_price)/entry*100)
        try:
            cost_pct=float(row.get("round_trip_cost_pct",DEFAULT_COST_POLICY.base_round_trip_pct))
            capital=float(row.get("capital_usd",500.0) or 500.0)
        except (TypeError,ValueError):
            cost_pct=DEFAULT_COST_POLICY.base_round_trip_pct
            capital=500.0
        if cost_pct < 0 or not math.isfinite(cost_pct):
            cost_pct=DEFAULT_COST_POLICY.base_round_trip_pct
        if capital <= 0 or not math.isfinite(capital):
            capital=500.0
        # Funding is not inferred from a single snapshot rate. Until a
        # complete, timestamp-aligned settlement is attached, this outcome is
        # explicitly incomplete and cannot train Outcome Memory.
        row.update({"status":status,"resolved_ts":now,"exit_price":exit_price,
                    "observed_price":price,
                    "gross_move_pct":round(gross_pct,6),
                    "round_trip_cost_pct":cost_pct,
                    "funding_status":row.get("funding_status","UNVERIFIED"),
                    "funding_coverage":float(row.get("funding_coverage",0.0) or 0.0),
                    "funding_cashflow_usd":row.get("funding_cashflow_usd"),
                    "net_profit_usd":round(capital*(gross_pct-cost_pct)/100,4),
                    "learning_eligible":False})
        changed+=1
    if changed:
        tmp=p.with_suffix(p.suffix+".tmp")
        tmp.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),encoding="utf-8")
        tmp.replace(p)
    return changed

def apply_funding_settlements(path: str, settlements: dict) -> int:
    """Attach verified, holding-period funding cashflows to resolved shadow rows.

    settlements maps signal_id to {coverage, events, cashflow_usd}. Cashflow is
    signed from the strategy's perspective: receipts are positive, payments
    are negative. Coverage below 95%, missing events, or invalid values are
    rejected and never make a sample eligible for learning.
    """
    p=Path(path)
    if not p.exists() or not isinstance(settlements,dict):
        return 0
    try:
        rows=[json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError,json.JSONDecodeError):
        return 0
    changed=0
    for row in rows:
        if row.get("status") not in ("TARGET","STOP"):
            continue
        settlement=settlements.get(row.get("signal_id"))
        if not isinstance(settlement,dict):
            continue
        try:
            coverage=float(settlement.get("coverage"))
            events=int(settlement.get("events"))
            cashflow=float(settlement.get("cashflow_usd"))
            capital=float(row.get("capital_usd",500.0) or 500.0)
            gross=float(row.get("gross_move_pct"))
            cost=float(row.get("round_trip_cost_pct",DEFAULT_COST_POLICY.base_round_trip_pct))
        except (TypeError,ValueError):
            continue
        if (not all(math.isfinite(v) for v in (coverage,cashflow,capital,gross,cost))
                or coverage < 0.95 or coverage > 1.0 or events < 1
                or capital <= 0 or cost < 0):
            continue
        row.update({
            "funding_status":"VERIFIED",
            "funding_coverage":round(coverage,6),
            "funding_events":events,
            "funding_cashflow_usd":round(cashflow,6),
            "funding_verified_ts":int(time.time()),
            "net_profit_usd":round(capital*(gross-cost)/100.0+cashflow,4),
            "learning_eligible":True,
        })
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
    empty={
        "count":0,"open":0,"resolved":0,"resolved_total":0,
        "funding_verified_resolved":0,"funding_incomplete_resolved":0,
        "wins":0,"losses":0,"win_rate":0.0,"net_profit_usd":0.0,
        "by_regime":{},"by_direction":{},
        "by_confidence":{},"by_economic_tier":{},
    }
    if not p.exists():
        return empty

    rows=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    resolved_all=[r for r in rows if r.get("status") in ("TARGET","STOP")]
    eligible=[
        r for r in resolved_all
        if r.get("funding_status")=="VERIFIED"
        and r.get("learning_eligible") is True
        and float(r.get("funding_coverage",0.0) or 0.0)>=0.95
        and r.get("funding_cashflow_usd") is not None
    ]
    wins=sum(r.get("status")=="TARGET" for r in eligible)
    losses=sum(r.get("status")=="STOP" for r in eligible)
    net=sum(float(r.get("net_profit_usd",0.0) or 0.0) for r in eligible)

    return {
        "count":len(rows),
        "open":sum(r.get("status")=="OPEN" for r in rows),
        "resolved":len(eligible),
        "resolved_total":len(resolved_all),
        "funding_verified_resolved":len(eligible),
        "funding_incomplete_resolved":len(resolved_all)-len(eligible),
        "wins":wins,
        "losses":losses,
        "win_rate":round(wins/len(eligible),4) if eligible else 0.0,
        "net_profit_usd":round(net,4),
        "by_regime":_group_outcomes(
            eligible, lambda r: str(r.get("regime","UNKNOWN")).upper() or "UNKNOWN"
        ),
        "by_direction":_group_outcomes(
            eligible, lambda r: str(r.get("direction","UNKNOWN")).upper() or "UNKNOWN"
        ),
        "by_confidence":_group_outcomes(
            eligible, lambda r: _bucket_confidence(r.get("confidence"))
        ),
        "by_economic_tier":_group_outcomes(
            eligible, lambda r: _bucket_economic(r.get("modeled_profit_usd"))
        ),
    }
