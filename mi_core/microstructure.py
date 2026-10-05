"""Research-only cross-exchange confirmation and microstructure scoring."""
from __future__ import annotations
from math import isfinite
from typing import Mapping, Sequence

def _clamp(value: float) -> float: return max(-1.0,min(1.0,float(value)))

def orderbook_imbalance(bid_size: float, ask_size: float) -> float:
    bid_size,ask_size=float(bid_size),float(ask_size)
    if bid_size<0 or ask_size<0: raise ValueError("order book sizes must be non-negative")
    total=bid_size+ask_size
    return 0.0 if total==0 else (bid_size-ask_size)/total

def microstructure_score(data: Mapping[str,float|int|None]) -> dict:
    imbalance=orderbook_imbalance(float(data.get("bid_size") or 0),float(data.get("ask_size") or 0))
    trade_flow=float(data.get("trade_flow") or 0); spread_bps=max(0.0,float(data.get("spread_bps") or 0))
    spread_score=_clamp(1.0-spread_bps/50.0)
    score=_clamp(0.50*imbalance+0.35*_clamp(trade_flow)+0.15*spread_score*(1 if imbalance>=0 else -1))
    return {"orderbook_imbalance":round(imbalance,6),"trade_flow":round(_clamp(trade_flow),6),"spread_bps":round(spread_bps,6),
            "score":round(score,6),"bias":"BULLISH" if score>=.20 else "BEARISH" if score<=-.20 else "NEUTRAL","diagnostic_only":True}

def cross_exchange_confirmation(snapshots: Sequence[Mapping[str,float|int|None]], *, min_exchanges:int=2) -> dict:
    if min_exchanges<1: raise ValueError("min_exchanges must be positive")
    valid=[]
    for item in snapshots:
        try: score=float(item.get("score"))
        except (TypeError,ValueError): continue
        if isfinite(score):
            quality=float(item.get("quality",1.0) or 0.0)
            valid.append((_clamp(score),max(0.0,min(1.0,quality))))
    if not valid:
        return {"score":0.0,"agreement":0.0,"exchanges":0,"qualified_exchanges":0,"confirmed":False,"bias":"NEUTRAL","diagnostic_only":True}
    bullish=sum(x>.15 for x,_ in valid); bearish=sum(x<-.15 for x,_ in valid); total=len(valid)
    qualified=sum(q>=.70 for _,q in valid)
    weighted=sum(x*q for x,q in valid)/max(0.001,sum(q for _,q in valid))
    if bullish>=bearish and bullish:
        agreement=bullish/total; bias="BULLISH"; confirmed=bullish>=min_exchanges and agreement>=.67 and qualified>=min_exchanges
    elif bearish:
        agreement=bearish/total; bias="BEARISH"; confirmed=bearish>=min_exchanges and agreement>=.67 and qualified>=min_exchanges
    else:
        agreement=1.0; bias="NEUTRAL"; confirmed=False
    return {"score":round(weighted,6),"agreement":round(agreement,6),"exchanges":total,"qualified_exchanges":qualified,
            "confirmed":confirmed,"bias":bias,"diagnostic_only":True}
