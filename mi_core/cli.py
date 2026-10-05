import argparse,json,math,time
from pathlib import Path
from .models import MarketBar
from .storage import append_jsonl,load_bars
from .data import load_csv
from .research import evaluate,train_test
from .dashboard import build_html
from .real_data import download as download_real
from .multi_exchange import fetch_snapshot,print_snapshot,DEFAULT_SYMBOLS,EXCHANGES
from .intelligence_pipeline import analyze_market
from .historical_validation import evaluate_historical_evidence
from .signal_report import render_signal_report
from .live_brain import run_once as run_live_brain, print_live as print_live_brain
from .project60_adapter import summarize as summarize_project60
from .persian_report import render_persian

def demo(out):
    p=Path(out); p.mkdir(parents=True,exist_ok=True); fp=p/"market.jsonl"; price=100.0
    for i in range(240):
        price*=1+0.002*math.sin(i/9)+0.001*math.sin(i/3)
        append_jsonl(fp,MarketBar(i,"BTCUSDT",price,volume=100+i%20,buy_volume=60+i%10,sell_volume=40,whale_buy=12+i%5,whale_sell=6,sentiment=.2).to_dict())
    print(fp)

def load_input(path):
    p=Path(path)
    return load_csv(p) if p.suffix.lower()==".csv" else load_bars(p)

def write_report(result,out,metadata=None):
    payload={"metadata":metadata or {},**result}
    out=Path(out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(out); return payload

def analyze(inp,out=None):
    bars=load_input(inp); result=train_test(bars)
    return write_report(result,out or Path(inp).with_suffix(".report.json"),{"mode":"file","bars":len(bars),"symbols":sorted({b.symbol for b in bars})})

def real(symbol,interval,bars,out,report):
    data_path=Path(out); fetched,data_path=download_real(symbol,interval,bars,str(data_path))
    if len(fetched)<2: raise RuntimeError("real-data download returned fewer than two usable bars")
    result=train_test(fetched)
    return write_report(result,report,{"mode":"real-market-data","venue":"Binance public market-data API","symbol":symbol.upper(),"interval":interval,"bars":len(fetched),"first_ts":fetched[0].ts,"last_ts":fetched[-1].ts,"data_path":str(data_path),"research_only":True,"live_orders":False})

def intelligence(inp,out=None,pretty=False):
    bars=load_input(inp)
    history=evaluate_historical_evidence(bars)
    result=analyze_market(bars, volume_history=[b.volume for b in bars[-21:-1]], historical_evidence=history)
    payload=write_report(result,out or Path(inp).with_suffix(".intelligence.json"),{"mode":"integrated-research","bars":len(bars),"historical_evidence":True,"research_only":True,"live_orders":False})
    if pretty and payload.get("final_report"):
        print("\n"+render_signal_report(payload["final_report"]))
    return payload

def dashboard(report,out):
    payload=json.loads(Path(report).read_text(encoding="utf-8")); print(build_html(payload,out))

def live(exchanges,symbols,interval,cycles):
    exchanges=[x.strip().lower() for x in exchanges.split(",") if x.strip()] if exchanges else list(EXCHANGES)
    symbols=[x.strip().upper().replace("-","") for x in symbols.split(",") if x.strip()] if symbols else list(DEFAULT_SYMBOLS)
    if interval<5: raise ValueError("interval must be at least 5 seconds")
    count=0
    print("Market Intelligence Core | LIVE PUBLIC MARKET DATA | research_only=True | live_orders=False")
    print("exchanges="+",".join(exchanges)); print("symbols="+",".join(symbols)); print("poll_seconds="+str(interval))
    while cycles==0 or count<cycles:
        print_snapshot(fetch_snapshot(symbols,exchanges))
        count+=1
        if cycles==0 or count<cycles: time.sleep(interval)

def main():
    ap=argparse.ArgumentParser(description="Market Intelligence Core")
    sp=ap.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo"); d.add_argument("--out",default="data/demo")
    a=sp.add_parser("analyze"); a.add_argument("--input",required=True); a.add_argument("--out")
    r=sp.add_parser("real"); r.add_argument("--symbol",default="BTCUSDT"); r.add_argument("--interval",default="1h"); r.add_argument("--bars",type=int,default=1000); r.add_argument("--out",default="data/real/btcusdt_1h.jsonl"); r.add_argument("--report",default="reports/real_btcusdt_1h.json")
    l=sp.add_parser("live"); l.add_argument("--exchanges",default=",".join(EXCHANGES)); l.add_argument("--symbols",default=",".join(DEFAULT_SYMBOLS)); l.add_argument("--interval",type=int,default=20); l.add_argument("--cycles",type=int,default=0)
    q=sp.add_parser("intelligence"); q.add_argument("--input",required=True); q.add_argument("--out"); q.add_argument("--pretty",action="store_true",help="print the concise manual-review signal report")
    h=sp.add_parser("dashboard"); h.add_argument("--report",required=True); h.add_argument("--out",default="reports/dashboard.html")
    z=sp.add_parser("live-all"); z.add_argument("--exchanges",default=",".join(EXCHANGES)); z.add_argument("--symbols",default=",".join(DEFAULT_SYMBOLS)); z.add_argument("--interval",type=int,default=30); z.add_argument("--cycles",type=int,default=0); z.add_argument("--fomo-chain",default="solana"); z.add_argument("--fomo-limit",type=int,default=5); z.add_argument("--project60-file",default="")
    x=ap.parse_args()
    if x.cmd=="demo": demo(x.out)
    elif x.cmd=="analyze": analyze(x.input,x.out)
    elif x.cmd=="real": real(x.symbol,x.interval,x.bars,x.out,x.report)
    elif x.cmd=="live": live(x.exchanges,x.symbols,x.interval,x.cycles)
    elif x.cmd=="intelligence": intelligence(x.input,x.out,x.pretty)
    elif x.cmd=="live-all":
        if x.interval<10: raise ValueError("interval must be at least 10 seconds")
        count=0
        while x.cycles==0 or count<x.cycles:
            snap=run_live_brain(x.symbols.split(","),x.exchanges.split(","),x.fomo_chain,x.fomo_limit)
            print_live_brain(snap)
            p60=summarize_project60(x.project60_file) if x.project60_file else None
            print(render_persian(snap,p60))
            count+=1
            if x.cycles==0 or count<x.cycles: time.sleep(x.interval)
    else: dashboard(x.report,x.out)

if __name__=="__main__": main()
