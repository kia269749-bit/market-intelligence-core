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
