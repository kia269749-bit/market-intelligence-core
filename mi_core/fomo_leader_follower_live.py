from __future__ import annotations
import json
from pathlib import Path
from .fomo_leader_follower import TraderFill, detect_leader_follower_events

def _rows(path):
    p=Path(path)
    if not p.exists(): return []
    out=[]
    with p.open("r",encoding="utf-8") as f:
        for line in f:
            try:
                x=json.loads(line)
            except json.JSONDecodeError:
                continue
            payload=x.get("payload",x)
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict) and ("trader_id" in payload or "owner" in payload):
                rows = [payload]
            elif isinstance(payload, dict):
                rows = payload.get("candidates", payload.get("fills", []))
            else:
                rows = []
            if isinstance(rows,list): out.extend(r for r in rows if isinstance(r,dict))
    return out

def read_fills(path,min_confidence=.70):
    fills=[]
    for r in _rows(path):
        trader=str(r.get("trader_id") or r.get("owner") or "")
        token=str(r.get("token") or r.get("token_mint") or "")
        direction=str(r.get("direction") or r.get("side") or "UNKNOWN").upper()
        ts=int(r.get("timestamp") or 0)
        amount=float(r.get("amount_usd") or r.get("quote_amount") or 0)
        conf=float(r.get("confidence") or 0)
        if trader and token and ts and amount>0 and direction in ("BUY","SELL") and conf>=min_confidence:
            fills.append(TraderFill(trader,token,ts,direction,amount,conf,r.get("tx_id") or r.get("signature")))
    return fills

def load_leader_scores(path):
    if not path or not Path(path).exists(): return {}
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        return {str(k):max(0.0,min(1.0,float(v))) for k,v in (data.items() if isinstance(data,dict) else [])}
    except (OSError,ValueError,TypeError): return {}

def summarize(path,scores_path="",window_seconds=300):
    fills=read_fills(path)
    scores=load_leader_scores(scores_path)
    events=detect_leader_follower_events(fills,scores,window_seconds=window_seconds)
    return {"available":bool(fills),"fill_count":len(fills),"leader_scores":len(scores),"leader_score_map":scores,"events":[e.to_dict() for e in events[:10]],"confirmed":len(events)>0,"research_only":True,"live_orders":False}
