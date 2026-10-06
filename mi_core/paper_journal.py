"""Tiny append-only shadow journal for live research signals."""
from __future__ import annotations
import json, time
from pathlib import Path

def append_signal(path: str, signal: dict) -> None:
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    record={"ts":int(time.time()),"status":"OPEN",**signal}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False)+"\n")

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

def summarize(path: str) -> dict:
    p=Path(path)
    if not p.exists(): return {"count":0,"resolved":0,"wins":0,"losses":0,"win_rate":0.0}
    rows=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: continue
    resolved=[r for r in rows if r.get("status") in ("TARGET","STOP")]
    wins=sum(r.get("status")=="TARGET" for r in resolved)
    losses=sum(r.get("status")=="STOP" for r in resolved)
    return {"count":len(rows),"resolved":len(resolved),"wins":wins,"losses":losses,
            "win_rate":round(wins/len(resolved),4) if resolved else 0.0}
