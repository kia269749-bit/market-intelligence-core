from .storage import append_jsonl,read_jsonl

def record(path,signal,outcome):
    append_jsonl(path,{"signal":signal.to_dict(),"outcome":outcome})

def summarize(path):
    rows=read_jsonl(path)
    pnls=[r.get("outcome",{}).get("pnl",0.0) for r in rows]
    wins=[p for p in pnls if p>0]
    return {"observations":len(pnls),"win_rate":len(wins)/len(pnls) if pnls else 0.0,"pnl":sum(pnls)}
