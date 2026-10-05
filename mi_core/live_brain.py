"""Single lightweight live coordinator for Market + FOMO evidence."""
from __future__ import annotations
import time
from .fomo_live import scan_boosted
from .multi_exchange import fetch_snapshot, DEFAULT_SYMBOLS, EXCHANGES

def _market_bias(snapshot):
    changes=[float(x["change_24h_pct"]) for x in snapshot.get("rows",[])
             if x.get("change_24h_pct") is not None]
    if not changes: return "NEUTRAL",0.25
    avg=sum(changes)/len(changes)
    if avg>=1.0: return "BULLISH",min(1.0,0.50+avg/20)
    if avg<=-1.0: return "BEARISH",min(1.0,0.50+abs(avg)/20)
    return "NEUTRAL",0.50

def run_once(symbols=None, exchanges=None, fomo_chain="solana", fomo_limit=5):
    market=fetch_snapshot(symbols or DEFAULT_SYMBOLS, exchanges or EXCHANGES)
    try:
        fomo=scan_boosted(chain=fomo_chain,limit=fomo_limit); fomo_error=None
    except Exception as exc:
        fomo={"ts":int(time.time()),"candidates":[],"research_only":True,"wallet_level":False}
        fomo_error=str(exc)
    bias,confidence=_market_bias(market)
    return {
        "ts":int(time.time()),"market":market,"fomo":fomo,
        "evidence":{"market":{"bias":bias,"confidence":round(confidence,4),
                              "sources":len(market.get("rows",[]))},
                    "fomo":{"candidates":len(fomo.get("candidates",[])),
                            "top":fomo.get("candidates",[])[:3],"wallet_level":False}},
        "architecture":"Project60 + FOMO + MarketBrain -> Evidence -> Risk/Validation",
        "research_only":True,"live_orders":False,"fomo_error":fomo_error}

def print_live(snapshot):
    e=snapshot["evidence"]
    print("\nMARKET BRAIN LIVE | {}".format(time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(snapshot["ts"]))))
    print("market_bias={} confidence={:.2f} market_sources={}".format(
        e["market"]["bias"],e["market"]["confidence"],e["market"]["sources"]))
    print("fomo_candidates={} wallet_level={}".format(e["fomo"]["candidates"],e["fomo"]["wallet_level"]))
    for i,row in enumerate(e["fomo"]["top"],1):
        print("  FOMO#{} {} score={} vol={:,.0f} chg={:.2f}%".format(
            i,row.get("token"),row.get("fomo_score"),row.get("volume_24h_usd",0),row.get("price_change_24h_pct",0)))
    if snapshot.get("fomo_error"): print("fomo_warning="+snapshot["fomo_error"])
