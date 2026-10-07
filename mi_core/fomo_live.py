"""Lightweight, read-only live FOMO market scanner.
Uses public DexScreener data only. Wallet-level leader/follower evidence still
requires transaction fills from a chain data source.
"""
from __future__ import annotations
import json, time
from urllib.request import Request, urlopen

DEX_BASE="https://api.dexscreener.com"
DEFAULT_TIMEOUT=4

def _get_json(path: str, timeout: int = DEFAULT_TIMEOUT):
    req=Request(DEX_BASE+path, headers={"User-Agent":"market-intelligence-core/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _num(value, default=0.0):
    try: return float(value)
    except (TypeError, ValueError): return default

def _score_pair(pair: dict) -> float:
    liq=_num((pair.get("liquidity") or {}).get("usd"))
    vol=_num((pair.get("volume") or {}).get("h24"))
    change=_num((pair.get("priceChange") or {}).get("h24"))
    tx=(pair.get("txns") or {}).get("h24") or {}
    buys=_num(tx.get("buys")); sells=_num(tx.get("sells"))
    buy_ratio=buys/(buys+sells) if buys+sells else 0.5
    liq_factor=min(1.0, liq/1_000_000)
    vol_factor=min(1.0, vol/5_000_000)
    momentum=max(0.0,min(1.0,(change+20.0)/80.0))
    flow=max(0.0,min(1.0,buy_ratio))
    return round(100*(0.30*liq_factor+0.30*vol_factor+0.20*momentum+0.20*flow),2)

def scan_tokens(addresses, chain=None, limit=10):
    rows=[]
    for address in addresses:
        data=_get_json("/latest/dex/tokens/"+address)
        for pair in data.get("pairs") or []:
            if chain and pair.get("chainId") != chain: continue
            row={
                "chain":pair.get("chainId"),"dex":pair.get("dexId"),
                "pair":pair.get("pairAddress"),
                "token":(pair.get("baseToken") or {}).get("symbol"),
                "token_address":(pair.get("baseToken") or {}).get("address"),
                "price_usd":_num(pair.get("priceUsd")),
                "liquidity_usd":_num((pair.get("liquidity") or {}).get("usd")),
                "volume_24h_usd":_num((pair.get("volume") or {}).get("h24")),
                "price_change_24h_pct":_num((pair.get("priceChange") or {}).get("h24")),
                "buys_24h":int(_num(((pair.get("txns") or {}).get("h24") or {}).get("buys"))),
                "sells_24h":int(_num(((pair.get("txns") or {}).get("h24") or {}).get("sells"))),
            }
            row["buy_sell_ratio"]=round(row["buys_24h"]/max(1,row["sells_24h"]),4)
            row["fomo_score"]=_score_pair(pair)
            rows.append(row)
    rows.sort(key=lambda x:(x["fomo_score"],x["volume_24h_usd"],x["liquidity_usd"]),reverse=True)
    return {"ts":int(time.time()),"candidates":rows[:max(1,limit)],
            "research_only":True,"wallet_level":False}

def scan_boosted(chain=None, limit=10):
    data=_get_json("/token-boosts/latest/v1")
    candidates=[]
    # Bound public API work so one slow cycle cannot fan out into dozens of
    # sequential token requests on a phone.
    max_boosts=max(3, min(12, int(limit)*2))
    for item in data[:max_boosts] if isinstance(data,list) else []:
        if chain and item.get("chainId") != chain: continue
        address=item.get("tokenAddress")
        if not address: continue
        try:
            candidates.extend(scan_tokens([address],chain=chain,limit=3)["candidates"])
        except Exception:
            continue
    candidates.sort(key=lambda x:(x["fomo_score"],x["volume_24h_usd"]),reverse=True)
    return {"ts":int(time.time()),"candidates":candidates[:max(1,limit)],
            "research_only":True,"wallet_level":False}

def compact_report(snapshot):
    out=["FOMO LIVE | research_only=True | wallet_level=False"]
    for i,row in enumerate(snapshot.get("candidates",[])[:10],1):
        out.append("{} {} {} score={} vol={:,.0f} liq={:,.0f} chg={:.2f}% buy/sell={:.2f}".format(
            i,row.get("token"),row.get("chain"),row.get("fomo_score"),
            row.get("volume_24h_usd",0),row.get("liquidity_usd",0),
            row.get("price_change_24h_pct",0),row.get("buy_sell_ratio",0)))
    if not snapshot.get("candidates"): out.append("No usable candidates.")
    return "\n".join(out)
