import json
import statistics
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","TRXUSDT"]
EXCHANGES = ("binance","coinbase","kraken","okx")

def _get_json(url, params=None, timeout=8):
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    req = Request(url, headers={"User-Agent":"market-intelligence-core/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _base(symbol):
    return symbol.upper().replace("-","").replace("/","").removesuffix("USDT").removesuffix("USD")

def _binance(symbol):
    data = _get_json("https://data-api.binance.vision/api/v3/ticker/24hr", {"symbol":symbol.upper()})
    return {"exchange":"binance","symbol":symbol.upper(),"price":float(data["lastPrice"]),"volume_24h":float(data["volume"]),"change_24h_pct":float(data["priceChangePercent"])}

def _coinbase(symbol):
    base=_base(symbol); data=_get_json(f"https://api.exchange.coinbase.com/products/{base}-USD/ticker")
    return {"exchange":"coinbase","symbol":symbol.upper(),"price":float(data["price"]),"volume_24h":float(data.get("volume",0.0)),"change_24h_pct":None}

def _kraken(symbol):
    base=_base(symbol); pair=("XBT" if base=="BTC" else base)+"USD"
    data=_get_json("https://api.kraken.com/0/public/Ticker", {"pair":pair})
    if data.get("error"): raise RuntimeError(";".join(data["error"]))
    row=next(iter(data["result"].values()))
    return {"exchange":"kraken","symbol":symbol.upper(),"price":float(row["c"][0]),"volume_24h":float(row["v"][1]),"change_24h_pct":None}

def _okx(symbol):
    base=_base(symbol); data=_get_json("https://www.okx.com/api/v5/market/ticker", {"instId":f"{base}-USDT"})
    if data.get("code")!="0" or not data.get("data"): raise RuntimeError(data.get("msg","OKX error"))
    row=data["data"][0]
    return {"exchange":"okx","symbol":symbol.upper(),"price":float(row["last"]),"volume_24h":float(row.get("vol24h",0.0)),"change_24h_pct":None}

FETCHERS={"binance":_binance,"coinbase":_coinbase,"kraken":_kraken,"okx":_okx}

def fetch_snapshot(symbols=None, exchanges=None):
    symbols=[s.upper().replace("-","") for s in (symbols or DEFAULT_SYMBOLS)]
    exchanges=[e.lower() for e in (exchanges or EXCHANGES)]
    rows=[]; errors=[]
    for exchange in exchanges:
        if exchange not in FETCHERS:
            errors.append({"exchange":exchange,"error":"unsupported_exchange"}); continue
        for symbol in symbols:
            try: rows.append(FETCHERS[exchange](symbol))
            except Exception as exc: errors.append({"exchange":exchange,"symbol":symbol,"error":str(exc)})
    by_symbol={}
    for row in rows: by_symbol.setdefault(row["symbol"],[]).append(row)
    aggregates=[]
    for symbol, items in sorted(by_symbol.items()):
        prices=[x["price"] for x in items]; median=statistics.median(prices)
        spread=(max(prices)-min(prices))/median if median else 0.0
        aggregates.append({"symbol":symbol,"sources":len(items),"median_price":median,"min_price":min(prices),"max_price":max(prices),"cross_exchange_spread_pct":spread*100})
    return {"ts_ms":int(time.time()*1000),"rows":rows,"aggregates":aggregates,"errors":errors}

def print_snapshot(snapshot):
    print(f"\nLIVE MARKET | ts_ms={snapshot['ts_ms']}")
    print("SYMBOL       MEDIAN PRICE        RANGE              SPREAD%   SOURCES")
    for a in snapshot["aggregates"]:
        print(f"{a['symbol']:<12}{a['median_price']:>18.8g}  {a['min_price']:>12.8g}..{a['max_price']:<12.8g} {a['cross_exchange_spread_pct']:>8.3f} {a['sources']:>7}")
    if snapshot["errors"]:
        print(f"warnings={len(snapshot['errors'])}")
        for e in snapshot["errors"][:8]: print("  ",e)
