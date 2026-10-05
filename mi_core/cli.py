import argparse,json,math
from pathlib import Path
from .models import MarketBar
from .storage import append_jsonl,load_bars
from .data import load_csv
from .research import make_signals,evaluate,train_test
from .dashboard import build_html

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

def analyze(inp,out=None):
    bars=load_input(inp); result=train_test(bars)
    out=Path(out or Path(inp).with_suffix(".report.json"))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(out)
    return result

def dashboard(report,out):
    payload=json.loads(Path(report).read_text(encoding="utf-8"))
    print(build_html(payload,out))

def main():
    ap=argparse.ArgumentParser(description="Market Intelligence Core")
    sp=ap.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo"); d.add_argument("--out",default="data/demo")
    a=sp.add_parser("analyze"); a.add_argument("--input",required=True); a.add_argument("--out")
    h=sp.add_parser("dashboard"); h.add_argument("--report",required=True); h.add_argument("--out",default="reports/dashboard.html")
    x=ap.parse_args()
    if x.cmd=="demo": demo(x.out)
    elif x.cmd=="analyze": analyze(x.input,x.out)
    else: dashboard(x.report,x.out)

if __name__=="__main__": main()
