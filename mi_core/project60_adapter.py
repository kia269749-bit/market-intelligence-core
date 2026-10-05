"""Read-only adapter for Project 60 snapshots."""
from __future__ import annotations
import json
from pathlib import Path

def _last_jsonl(path):
    p=Path(path)
    if not p.exists(): return None
    last=None
    with p.open("r",encoding="utf-8",errors="ignore") as f:
        for line in f:
            line=line.strip()
            if line:
                try: last=json.loads(line)
                except json.JSONDecodeError: pass
    return last

def _walk(obj,wanted,out):
    if isinstance(obj,dict):
        for k,v in obj.items():
            key=str(k).lower()
            if key in wanted and v is not None: out[key]=v
            _walk(v,wanted,out)
    elif isinstance(obj,list):
        for v in obj: _walk(v,wanted,out)

def read_snapshot(path):
    raw=_last_jsonl(path)
    if not raw: return {"available":False,"reason":"no_snapshot"}
    wanted={"timestamp","datetime","price","oi","open_interest","funding","funding_rate","orderbook","order_book","tradeflow","trade_flow","flow","symbol","coin"}
    found={}
    _walk(raw,wanted,found)
    return {"available":True,"raw":raw,"fields":found}

def summarize(path):
    data=read_snapshot(path)
    if not data.get("available"): return data
    fields=data["fields"]
    text=json.dumps(data["raw"],ensure_ascii=False).lower()
    return {"available":True,"timestamp":fields.get("timestamp"),"datetime":fields.get("datetime"),
            "has_oi":"oi" in fields or "open_interest" in fields or "open_interest" in text,
            "has_funding":"funding" in fields or "funding_rate" in fields,
            "has_orderbook":"orderbook" in fields or "order_book" in fields or "orderbook" in text,
            "has_tradeflow":"tradeflow" in fields or "trade_flow" in fields or "tradeflow" in text,
            "fields":fields}


def _direction(raw):
    text=json.dumps(raw,ensure_ascii=False).lower()
    bull=any(x in text for x in ("bullish","buy_pressure","buying_pressure","net_buy"))
    bear=any(x in text for x in ("bearish","sell_pressure","selling_pressure","net_sell"))
    if bull and not bear: return "BULLISH"
    if bear and not bull: return "BEARISH"
    return "UNKNOWN"


def _confidence(raw):
    if isinstance(raw,dict):
        for k,v in raw.items():
            if str(k).lower() in ("confidence","signal_confidence"):
                try:
                    n=float(v); return max(0.0,min(1.0,n/100 if n>1 else n))
                except (TypeError,ValueError): pass
            c=_confidence(v)
            if c: return c
    elif isinstance(raw,list):
        for v in raw:
            c=_confidence(v)
            if c: return c
    return 0.0


def live_evidence(path):
    data=read_snapshot(path)
    if not data.get("available"):
        return {"available":False,"bias":"UNKNOWN","confidence":0.0}
    return {"available":True,"bias":_direction(data.get("raw",{})),
            "confidence":_confidence(data.get("raw",{})),
            "assets":data.get("assets",{}),
            "timestamp":data.get("timestamp")}
