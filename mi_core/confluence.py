"""Research-only multi-layer confluence scoring."""
from __future__ import annotations

def _direction(score:float)->int:
    return 1 if score>0 else -1 if score<0 else 0

def confluence_score(signal_score:float,flow_score:float,positioning_score:float,microstructure_score:float,
                     exchange_score:float,exchange_quality:float=1.0)->dict:
    values=[float(signal_score),float(flow_score),float(positioning_score),float(microstructure_score),float(exchange_score)]
    values=[max(-1.0,min(1.0,x)) for x in values]
    exchange_quality=max(0.0,min(1.0,float(exchange_quality)))
    weights=[0.30,0.20,0.20,0.15,0.15]
    weights[-1]*=exchange_quality
    total=sum(weights) or 1.0
    weights=[w/total for w in weights]
    score=sum(v*w for v,w in zip(values,weights))
    directional=[_direction(v) for v in values if _direction(v)]
    agreement=max(directional.count(1),directional.count(-1))/len(directional) if directional else 0.0
    effective_score=score*agreement
    return {"score":round(score,6),"effective_score":round(effective_score,6),
            "bias":"BULLISH" if score>=.20 else "BEARISH" if score<=-.20 else "NEUTRAL",
            "effective_bias":"BULLISH" if effective_score>=.20 else "BEARISH" if effective_score<=-.20 else "NEUTRAL",
            "agreement":round(agreement,6),"conflict_penalty":round(1-agreement,6),
            "layers":len(values),"exchange_quality":round(exchange_quality,6),"diagnostic_only":True}
