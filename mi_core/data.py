import csv
from pathlib import Path
from .models import MarketBar

REQUIRED={"ts","symbol","price"}

def validate_bar(row):
    if not REQUIRED.issubset(row): return False
    try: return int(row["ts"])>=0 and float(row["price"])>0 and bool(row["symbol"])
    except (TypeError,ValueError): return False

def load_csv(path):
    rows=[]
    with Path(path).open(newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not validate_bar(row): continue
            def num(k,d=0.0):
                v=row.get(k,""); return d if v in ("",None) else float(v)
            rows.append(MarketBar(ts=int(row["ts"]),symbol=row["symbol"],price=float(row["price"]),
                volume=num("volume"),oi=None if row.get("oi","")=="" else num("oi"),
                funding=None if row.get("funding","")=="" else num("funding"),
                bid=None if row.get("bid","")=="" else num("bid"),ask=None if row.get("ask","")=="" else num("ask"),
                buy_volume=num("buy_volume"),sell_volume=num("sell_volume"),whale_buy=num("whale_buy"),
                whale_sell=num("whale_sell"),sentiment=num("sentiment")))
    return sorted(rows,key=lambda x:(x.symbol,x.ts))
