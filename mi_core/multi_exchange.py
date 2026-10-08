import json
import statistics
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","TRXUSDT"]
EXCHANGES = ("binance","coinbase","kraken","okx")
MIN_SOURCES_PER_SYMBOL = 2

def _get_json(url, params=None, timeout=8):
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    req = Request(url, headers={"User-Agent":"market-intelligence-core/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _base(symbol):
    value = symbol.upper().replace("-","").replace("/","")
    for quote in ("USDT","USDC","USD"):
        if value.endswith(quote):
            return value[:-len(quote)]
    return value

def _binance(symbol):
    data = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", {"symbol":symbol.upper()})
    return {"exchange":"binance","symbol":symbol.upper(),"price":float(data["lastPrice"]),"volume_24h":float(data["volume"]),"change_24h_pct":float(data["priceChangePercent"]),"timestamp":time.time()}

def _coinbase(symbol):
    base=_base(symbol)
    data=_get_json(f"https://api.exchange.coinbase.com/products/{base}-USD/ticker")
    return {"exchange":"coinbase","symbol":symbol.upper(),"price":float(data["price"]),"volume_24h":float(data.get("volume",0.0)),"change_24h_pct":None,"timestamp":time.time()}

def _kraken(symbol):
    base=_base(symbol)
    aliases={"BTC":"XBT","DOGE":"XDG"}
    pair=(aliases.get(base,base))+"USD"
    data=_get_json("https://api.kraken.com/0/public/Ticker", {"pair":pair})
    if data.get("error"): raise RuntimeError(";".join(data["error"]))
    row=next(iter(data["result"].values()))
    return {"exchange":"kraken","symbol":symbol.upper(),"price":float(row["c"][0]),"volume_24h":float(row["v"][1]),"change_24h_pct":None,"timestamp":time.time()}

def _okx(symbol):
    base=_base(symbol)
    data=_get_json("https://www.okx.com/api/v5/market/ticker", {"instId":f"{base}-USDT"})
    if data.get("code")!="0" or not data.get("data"): raise RuntimeError(data.get("msg","OKX error"))
    row=data["data"][0]
    return {"exchange":"okx","symbol":symbol.upper(),"price":float(row["last"]),"volume_24h":float(row.get("vol24h",0.0)),"change_24h_pct":None,"timestamp":time.time()}

FETCHERS={"binance":_binance,"coinbase":_coinbase,"kraken":_kraken,"okx":_okx}

def _build_quality(symbols, exchanges, rows, errors):
    expected=len(symbols)*len(exchanges)
    successful=len(rows)
    success_ratio=(successful/expected) if expected else 0.0

    by_symbol={symbol:[] for symbol in symbols}
    for row in rows:
        by_symbol.setdefault(row["symbol"],[]).append(row)

    aggregates=[]
    for symbol in sorted(by_symbol):
        items=by_symbol[symbol]
        if items:
            prices=[x["price"] for x in items]
            median=statistics.median(prices)
            spread=(max(prices)-min(prices))/median if median else 0.0
            sources=sorted({str(x.get("exchange","")).lower() for x in items})
            aggregates.append({
                "symbol":symbol,
                "sources":len(sources),
                "source_names":sources,
                "median_price":median,
                "min_price":min(prices),
                "max_price":max(prices),
                "cross_exchange_spread_pct":spread*100,
            })
        else:
            aggregates.append({
                "symbol":symbol,
                "sources":0,
                "source_names":[],
                "median_price":None,
                "min_price":None,
                "max_price":None,
                "cross_exchange_spread_pct":None,
            })

    healthy_symbols=sum(1 for a in aggregates if a["sources"]>=3)
    degraded_symbols=sum(1 for a in aggregates if a["sources"]==2)
    unsafe_symbols=sum(1 for a in aggregates if a["sources"]<MIN_SOURCES_PER_SYMBOL)
    covered_symbols=sum(1 for a in aggregates if a["sources"]>0)

    error_counts={}
    for err in errors:
        ex=str(err.get("exchange","unknown"))
        error_counts[ex]=error_counts.get(ex,0)+1

    if successful==0 or unsafe_symbols>len(aggregates)*0.5:
        data_quality="UNSAFE"
    elif successful < expected*0.75 or degraded_symbols>0:
        data_quality="DEGRADED"
    else:
        data_quality="HEALTHY"

    quality={
        "status":data_quality,
        "expected_sources":expected,
        "successful_sources":successful,
        "success_ratio":success_ratio,
        "requested_symbols":len(symbols),
        "covered_symbols":covered_symbols,
        "healthy_symbols":healthy_symbols,
        "degraded_symbols":degraded_symbols,
        "unsafe_symbols":unsafe_symbols,
        "min_sources_per_symbol":MIN_SOURCES_PER_SYMBOL,
        "exchange_errors":error_counts,
    }
    return aggregates,quality

def fetch_snapshot(symbols=None, exchanges=None):
    symbols=[s.upper().replace("-","") for s in (symbols or DEFAULT_SYMBOLS)]
    exchanges=[e.lower() for e in (exchanges or EXCHANGES)]
    rows=[]; errors=[]

    for exchange in exchanges:
        if exchange not in FETCHERS:
            errors.append({"exchange":exchange,"error":"unsupported_exchange"})
            continue
        for symbol in symbols:
            try:
                rows.append(FETCHERS[exchange](symbol))
            except Exception as exc:
                errors.append({"exchange":exchange,"symbol":symbol,"error":str(exc)})

    aggregates,quality=_build_quality(symbols,exchanges,rows,errors)
    return {"ts_ms":int(time.time()*1000),"rows":rows,"aggregates":aggregates,"errors":errors,"data_quality":quality}

def print_snapshot(snapshot):
    print(f"\nLIVE MARKET | ts_ms={snapshot['ts_ms']}")
    q=snapshot.get("data_quality",{})
    if q:
        print("🧪 سلامت داده | وضعیت={} | منابع موفق={}/{} ({:.0f}٪) | پوشش نماد={}/{} | سالم={} کاهش‌یافته={} ناامن={} | حداقل منابع/نماد={}".format(
            q.get("status","UNKNOWN"),q.get("successful_sources",0),q.get("expected_sources",0),
            q.get("success_ratio",0.0)*100,q.get("covered_symbols",0),q.get("requested_symbols",0),
            q.get("healthy_symbols",0),q.get("degraded_symbols",0),q.get("unsafe_symbols",0),
            q.get("min_sources_per_symbol",MIN_SOURCES_PER_SYMBOL)))
    print("SYMBOL       MEDIAN PRICE        RANGE              SPREAD%   SOURCES")
    for a in snapshot["aggregates"]:
        if a["median_price"] is None:
            print(f"{a['symbol']:<12}{'N/A':>18}  {'N/A':>12}..{'N/A':<12} {'N/A':>8} {a['sources']:>7}")
        else:
            print(f"{a['symbol']:<12}{a['median_price']:>18.8g}  {a['min_price']:>12.8g}..{a['max_price']:<12.8g} {a['cross_exchange_spread_pct']:>8.3f} {a['sources']:>7}")
    if snapshot["errors"]:
        counts={}
        for e in snapshot["errors"]:
            key=(e.get("exchange","unknown"),e.get("error","unknown"))
            counts[key]=counts.get(key,0)+1
        print(f"⚠️ هشدارهای داده={len(snapshot['errors'])} | خطاهای یکتا={len(counts)}")
        for (exchange,error),n in list(counts.items())[:8]:
            print("  {} x{} | {}".format(exchange,n,error))
