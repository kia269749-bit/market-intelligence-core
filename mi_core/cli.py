import argparse,json,math
from pathlib import Path
from .models import MarketBar
from .storage import append_jsonl,load_bars
from .data import load_csv
from .research import evaluate,train_test
from .dashboard import build_html
from .real_data import download as download_real

def demo(out):
    p=Path(out); p.mkdir(parents=True,exist_ok=True); fp=p/"market.jsonl"; price=100.0
    for i in range(240):
        price*=1+0.002*math.sin(i/9)+0.001*math.sin(i/3)
        append_jsonl(fp,MarketBar(i,"BTCUSDT",price,volume=100+i%20,buy_volume=60+i%10,
            sell_volume=40,whale_buy=12+i%5,whale_sell=6,sentiment=.2).to_dict())
    print(fp)

def load_input(path):
    p=Path(path)
    return load_csv(p) if p.suffix.lower()==".csv" else load_bars(p)

def write_report(result,out,metadata=None):
    payload={"metadata":metadata or {},**result}
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(out)
    return payload

def analyze(inp,out=None):
    bars=load_input(inp)
    result=train_test(bars)
    return write_report(result,out or Path(inp).with_suffix(".report.json"),
                        {"mode":"file","bars":len(bars),"symbols":sorted({b.symbol for b in bars})})

def real(symbol,interval,bars,out,report):
    data_path=Path(out)
    fetched,data_path=download_real(symbol,interval,bars,str(data_path))
    if len(fetched)<2:
        raise RuntimeError("real-data download returned fewer than two usable bars")
    result=train_test(fetched)
    return write_report(result,report,
        {"mode":"real-market-data","venue":"Binance public market-data API",
         "symbol":symbol.upper(),"interval":interval,"bars":len(fetched),
         "first_ts":fetched[0].ts,"last_ts":fetched[-1].ts,
         "data_path":str(data_path),
         "research_only":True,"live_orders":False})

def dashboard(report,out):
    payload=json.loads(Path(report).read_text(encoding="utf-8"))
    print(build_html(payload,out))

def main():
    ap=argparse.ArgumentParser(description="Market Intelligence Core")
    sp=ap.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo"); d.add_argument("--out",default="data/demo")
    a=sp.add_parser("analyze"); a.add_argument("--input",required=True); a.add_argument("--out")
    r=sp.add_parser("real")
    r.add_argument("--symbol",default="BTCUSDT")
    r.add_argument("--interval",default="1h")
    r.add_argument("--bars",type=int,default=1000)
    r.add_argument("--out",default="data/real/btcusdt_1h.jsonl")
    r.add_argument("--report",default="reports/real_btcusdt_1h.json")
    h=sp.add_parser("dashboard"); h.add_argument("--report",required=True); h.add_argument("--out",default="reports/dashboard.html")
    x=ap.parse_args()
    if x.cmd=="demo": demo(x.out)
    elif x.cmd=="analyze": analyze(x.input,x.out)
    elif x.cmd=="real": real(x.symbol,x.interval,x.bars,x.out,x.report)
    else: dashboard(x.report,x.out)

if __name__=="__main__": main()
