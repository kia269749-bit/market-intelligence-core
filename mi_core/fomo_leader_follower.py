from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Sequence
from .fomo_direction import TradeDirection
@dataclass(frozen=True)
class TraderFill:
    trader_id:str;token:str;timestamp:int;direction:TradeDirection|str;amount_usd:float;confidence:float=1.0;tx_id:str|None=None
    def normalized_direction(self):
        try:return self.direction if isinstance(self.direction,TradeDirection) else TradeDirection(str(self.direction).upper())
        except ValueError:return TradeDirection.UNKNOWN
@dataclass(frozen=True)
class LeaderFollowerEvent:
    leader_id:str;token:str;direction:TradeDirection;leader_timestamp:int;leader_amount_usd:float;leader_score:float;follower_ids:tuple[str,...];follower_count:int;follower_volume_usd:float;median_lag_seconds:float;confidence:float;status:str
    def to_dict(self):return {"leader_id":self.leader_id,"token":self.token,"direction":self.direction.value,"leader_timestamp":self.leader_timestamp,"leader_amount_usd":self.leader_amount_usd,"leader_score":self.leader_score,"follower_ids":list(self.follower_ids),"follower_count":self.follower_count,"follower_volume_usd":self.follower_volume_usd,"median_lag_seconds":self.median_lag_seconds,"confidence":self.confidence,"status":self.status}
def _clip(v):return max(0.0,min(1.0,float(v)))
def detect_leader_follower_events(fills:Sequence[TraderFill],leader_scores:Mapping[str,float],*,window_seconds=300,min_leader_score=.60,min_fill_confidence=.60,min_followers=2):
    ordered=sorted(fills,key=lambda f:(int(f.timestamp),f.trader_id));out=[]
    for leader in ordered:
        direction=leader.normalized_direction();score=_clip(leader_scores.get(leader.trader_id,0))
        if direction is TradeDirection.UNKNOWN or score<min_leader_score or leader.confidence<min_fill_confidence:continue
        unique={}
        for c in ordered:
            if c.trader_id==leader.trader_id or c.token!=leader.token or c.normalized_direction() is not direction or c.confidence<min_fill_confidence:continue
            lag=int(c.timestamp)-int(leader.timestamp)
            if 0<lag<=window_seconds:unique.setdefault(c.trader_id,c)
        if len(unique)<min_followers:continue
        lags=sorted(int(f.timestamp)-int(leader.timestamp) for f in unique.values());mid=len(lags)//2;median=float(lags[mid]) if len(lags)%2 else (lags[mid-1]+lags[mid])/2
        volume=sum(max(0,float(f.amount_usd)) for f in unique.values());breadth=_clip(len(unique)/5);conf=_clip(.45*score+.25*leader.confidence+.20*breadth+.10*_clip(1-median/max(1,window_seconds)))
        out.append(LeaderFollowerEvent(leader.trader_id,leader.token,direction,int(leader.timestamp),float(leader.amount_usd),round(score,6),tuple(unique),len(unique),round(volume,6),median,round(conf,6),"LEADER_FOLLOWER_CONFIRMED"))
    return sorted(out,key=lambda e:(e.token,e.leader_timestamp,-e.confidence))
