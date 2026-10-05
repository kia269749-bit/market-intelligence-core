import argparse, math
from pathlib import Path
from .models import MarketBar
from .storage import append_jsonl, load_bars
from .intelligence import score_bar
from .backtest import run
from .report import write_report

def demo(out):
    p=Path(out); p.mkdir(parents=True,exist_ok=True); fp=p/"market.jsonl"
    price=100.0
    for i in range(240):
        price *= 1+0.002*math.sin(i/9)+0.001*math.sin(i/3)
        b=MarketBar(i,"BTCUSDT",price,volume=100+i%20,buy_volume=60+i%10,sell_volume=40,whale_buy=12+i%5,whale_sell=6,sentiment=0.2)
        append_jsonl(fp,b.to_dict())
    print(fp)

def analyze(inp):
    bars=load_bars(inp)
    sig=[score_bar(b,bars[max(0,i-20):i]) for i,b in enumerate(bars)]
    r=run(bars,sig)
    out=Path(inp).with_suffix(".report.json")
    print(write_report(out,r)); print(out)

def main():
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo"); d.add_argument("--out",default="data/demo")
    a=sp.add_parser("analyze"); a.add_argument("--input",required=True)
    x=ap.parse_args()
    demo(x.out) if x.cmd=="demo" else analyze(x.input)

if __name__=="__main__": main()
