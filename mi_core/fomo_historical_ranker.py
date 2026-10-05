from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Iterable

from .fomo_normalizer import FomoTraderSnapshot


def historical_fomo_rank(snapshots: Iterable[FomoTraderSnapshot], min_snapshots: int = 3) -> list[dict]:
    grouped = defaultdict(list)
    for s in snapshots: grouped[s.trader_id].append(s)
    ranked=[]
    for trader_id, rows in grouped.items():
        rows=sorted(rows,key=lambda x:x.captured_at)
        if len(rows)<min_snapshots: continue
        ranks=[r.rank for r in rows]
        pnls=[r.pnl_usd for r in rows]
        volumes=[r.volume_usd for r in rows]
        trades=[r.trades for r in rows]
        best_rank=max(1,min(ranks))
        rank_score=1.0-(mean(ranks)-1.0)/max(1.0,max(ranks)-1.0)
        pnl_positive=sum(1 for x in pnls if x>0)/len(pnls)
        pnl_trend=0.0 if len(pnls)<2 else max(-1.0,min(1.0,(pnls[-1]-pnls[0])/(abs(pnls[0])+1.0)))
        volume_presence=sum(1 for x in volumes if x>0)/len(volumes)
        activity_presence=sum(1 for x in trades if x>0)/len(trades)
        persistence=len(rows)
        score=max(0.0,min(1.0,0.35*rank_score+0.25*pnl_positive+0.15*max(0.0,pnl_trend)+0.15*volume_presence+0.10*activity_presence))
        ranked.append({'trader_id':trader_id,'snapshots':persistence,'avg_rank':round(mean(ranks),3),'best_rank':best_rank,'pnl_usd_latest':pnls[-1],'pnl_positive_rate':round(pnl_positive,4),'pnl_trend':round(pnl_trend,4),'avg_volume_usd':round(mean(volumes),2),'avg_trades':round(mean(trades),2),'historical_score':round(score,6)})
    ranked.sort(key=lambda x:(x['historical_score'],x['pnl_usd_latest']),reverse=True)
    for i,row in enumerate(ranked,1): row['rank']=i
    return ranked