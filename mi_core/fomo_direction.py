from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from math import isfinite
class TradeDirection(str, Enum):
    BUY="BUY"; SELL="SELL"; UNKNOWN="UNKNOWN"
@dataclass(frozen=True)
class DirectionEvidence:
    source:str; direction:TradeDirection; strength:float; detail:str=""
def _clip(v):
    try:
        number = float(v)
    except (TypeError, ValueError):
        return 0.0
    if not isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))
def infer_direction(*,target_token_delta:float,quote_token_delta:float|None=None,dex_direction=None,pool_direction=None,clmm_is_base_input=None,min_reliable_confidence=.60):
    ev=[]
    if target_token_delta>0: ev.append(DirectionEvidence("token_delta",TradeDirection.BUY,1.0 if quote_token_delta is not None and quote_token_delta<0 else .70))
    elif target_token_delta<0: ev.append(DirectionEvidence("token_delta",TradeDirection.SELL,1.0 if quote_token_delta is not None and quote_token_delta>0 else .70))
    for source,value in (("dex",dex_direction),("pool_vault",pool_direction)):
        try:d=TradeDirection(str(value).upper())
        except (ValueError,TypeError):continue
        if d in (TradeDirection.BUY,TradeDirection.SELL):ev.append(DirectionEvidence(source,d,.95))
    if clmm_is_base_input is not None:ev.append(DirectionEvidence("clmm_is_base_input",TradeDirection.BUY if clmm_is_base_input else TradeDirection.SELL,.80))
    if not ev:return {"direction":"UNKNOWN","confidence":0.0,"reliable":False}
    buy=sum(x.strength for x in ev if x.direction is TradeDirection.BUY);sell=sum(x.strength for x in ev if x.direction is TradeDirection.SELL)
    winner=TradeDirection.BUY if buy>sell else TradeDirection.SELL;total=buy+sell;agreement=(buy if winner is TradeDirection.BUY else sell)/total if total else 0
    count=sum(x.direction is winner for x in ev);conf=_clip((.65+.15*min(2,max(0,count-1)))*agreement);reliable=conf>=min_reliable_confidence and agreement>=.65
    if not reliable:winner=TradeDirection.UNKNOWN
    return {"direction":winner.value,"confidence":round(conf,6),"reliable":reliable,"evidence":[{"source":x.source,"direction":x.direction.value,"strength":x.strength} for x in ev]}
