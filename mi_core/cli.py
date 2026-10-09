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
from .live_brain import _path_forecast_from_project60, run_once as run_live_brain, print_live as print_live_brain, _validated_forecast_from_project60, _forecast_from_project60
from .project60_adapter import summarize as summarize_project60
from .persian_report import render_persian
from .fomo_leader_follower_live import summarize as summarize_fomo_leader_follower
from .paper_journal import summarize as summarize_paper_journal, append_signal as append_paper_signal, resolve_open_signals
from .shadow_performance import summarize_performance, format_performance_line
from .validated_forecast import walk_forward_forecast, score_predictions, score_capital_targets, forecast_acceptance_gate
from .multi_asset_forecast import scan_project60, load_project60_assets
from .context_brain import analyze_market_context
from .candle_brain import analyze_project60 as analyze_candle_brain
from .economic_edge import diagnose_economic_edge
from .real_validation import _non_overlapping_result, _directional_metrics

def _num(value, default=0.0):
    try:
        value=float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default

def demo(out):
    p=Path(out); p.mkdir(parents=True,exist_ok=True); fp=p/"market.jsonl"; price=100.0
    for i in range(240):
        price*=1+0.002*math.sin(i/9)+0.001*math.sin(i/3)
        append_jsonl(fp,MarketBar(i,"BTCUSDT",price,volume=100+i%20,buy_volume=60+i%10,sell_volume=40,whale_buy=12+i%5,whale_sell=6,sentiment=.2).to_dict())
    print(fp)

def load_project60_bars(path, asset="BTC", max_rows=800):
    rows=[]
    for line in Path(path).read_text(encoding="utf-8").splitlines()[-max_rows:]:
        try:
            x=json.loads(line); coins=x.get("coins",{})
            if isinstance(coins,list): coins={str(v.get("coin")):v for v in coins if isinstance(v,dict)}
            a=coins.get(asset) or coins.get(asset.upper())
            if not isinstance(a,dict): continue
            tr=a.get("trades") or {}; ob=a.get("orderbook") or {}
            price=float(a.get("price") or 0)
            if price<=0: continue
            rows.append(MarketBar(int(float(x.get("timestamp",0))),asset,price,
                oi=float(a["open_interest"]) if a.get("open_interest") is not None else None,
                funding=float(a["funding"]) if a.get("funding") is not None else None,
                bid=float(ob.get("bid_usd") or 0),ask=float(ob.get("ask_usd") or 0),
                buy_volume=float(tr.get("buy_usd") or 0),sell_volume=float(tr.get("sell_usd") or 0)))
        except (TypeError,ValueError,json.JSONDecodeError): continue
    return rows

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

def _append_shadow_if_actionable(journal_path, snapshot):
    """Append only an approved, actionable research signal to the shadow journal."""
    if not journal_path:
        return False
    combined=(snapshot.get("evidence") or {}).get("combined") or {}
    economics=snapshot.get("capital_economics") or {}
    forecast=(snapshot.get("evidence") or {}).get("forecast") or {}
    selected=forecast.get("selected") if isinstance(forecast,dict) else {}
    path_economics=(forecast.get("economic") or {}) if isinstance(forecast,dict) else {}
    edge=path_economics.get("best") or selected or {}
    if not combined.get("actionable"):
        return False
    if str(edge.get("tier","REJECT")) not in ("STRONG","VIABLE"):
        return False
    bias=str(combined.get("bias","")).upper()
    if bias not in ("BULLISH","BEARISH"):
        return False
    if not isinstance(selected,dict):
        selected={}
    entry_price=forecast.get("current_price") or selected.get("current_price") or edge.get("current_price")
    asset=str(forecast.get("asset") or selected.get("asset") or edge.get("asset") or "MARKET")
    try:
        entry_price=float(entry_price)
    except (TypeError,ValueError):
        entry_price=None
    if entry_price is None or entry_price <= 0:
        return False
    signal_id=f"{asset}:{bias}:{round(entry_price,4)}"
    try:
        existing=Path(journal_path)
        if existing.exists():
            for line in existing.read_text(encoding="utf-8").splitlines():
                try:
                    row=json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("status")!="OPEN": continue
                same_id=row.get("signal_id")==signal_id
                try:
                    same_setup=(
                        str(row.get("asset","" )).upper()==asset.upper()
                        and str(row.get("direction","" )).upper()==bias
                        and abs(float(row.get("entry_price",0.0))-entry_price) <= max(entry_price*0.0001, 1e-12)
                    )
                except (TypeError,ValueError):
                    same_setup=False
                if same_id or same_setup:
                    return False
    except OSError:
        pass
    target_pct=max(0.0,_num(edge.get("selected_target_pct",0.0)))
    adverse_pct=max(0.0,_num(selected.get("adverse_move_pct",0.0)))
    if target_pct<=0.0:
        return False
    stop_pct=max(0.10,min(5.0,adverse_pct if adverse_pct>0 else target_pct*0.75))
    target_price=entry_price*(1.0+target_pct/100.0) if bias=="BULLISH" else entry_price*(1.0-target_pct/100.0)
    stop_price=entry_price*(1.0-stop_pct/100.0) if bias=="BULLISH" else entry_price*(1.0+stop_pct/100.0)
    signal={
        "signal_id":signal_id,
        "asset":asset,
        "direction":bias,
        "entry_price":entry_price,
        "target":target_price,
        "stop":stop_price,
        "target_pct":target_pct,
        "stop_pct":stop_pct,
        "round_trip_cost_pct":0.35,
        "capital_usd":500.0,
        "expected_move_pct":edge.get("expected_return_pct",edge.get("expected_move_pct")),
        "selected_target_pct":target_pct,
        "selected_target_hit_probability":edge.get("selected_target_hit_probability"),
        "expected_net_return_pct":edge.get("expected_net_return_pct"),
        "capital_reporting":economics,
        "confidence":combined.get("confidence"),
        "agreement":combined.get("agreement"),
        "regime":combined.get("regime"),
        "quality":(snapshot.get("evidence") or {}).get("data_quality",{}).get("status"),
        "forecast":forecast,
        "research_only":True,
        "live_orders":False,
    }
    append_paper_signal(journal_path,signal)
    return True

def main():
    ap=argparse.ArgumentParser(description="Market Intelligence Core")
    sp=ap.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo"); d.add_argument("--out",default="data/demo")
    a=sp.add_parser("analyze"); a.add_argument("--input",required=True); a.add_argument("--out")
    r=sp.add_parser("real"); r.add_argument("--symbol",default="BTCUSDT"); r.add_argument("--interval",default="1h"); r.add_argument("--bars",type=int,default=1000); r.add_argument("--out",default="data/real/btcusdt_1h.jsonl"); r.add_argument("--report",default="reports/real_btcusdt_1h.json")
    l=sp.add_parser("live"); l.add_argument("--exchanges",default=",".join(EXCHANGES)); l.add_argument("--symbols",default=",".join(DEFAULT_SYMBOLS)); l.add_argument("--interval",type=int,default=20); l.add_argument("--cycles",type=int,default=0)
    q=sp.add_parser("intelligence"); q.add_argument("--input",required=True); q.add_argument("--out"); q.add_argument("--pretty",action="store_true",help="print the concise manual-review signal report")
    h=sp.add_parser("dashboard"); h.add_argument("--report",required=True); h.add_argument("--out",default="reports/dashboard.html")
    v=sp.add_parser("forecast-validate"); v.add_argument("--input",required=True); v.add_argument("--horizon",type=int,default=60); v.add_argument("--train-window",type=int,default=300); v.add_argument("--out")
    pv=sp.add_parser("forecast-project60"); pv.add_argument("--input",required=True); pv.add_argument("--asset",default="BTC"); pv.add_argument("--horizon",type=int,default=60); pv.add_argument("--max-rows",type=int,default=800); pv.add_argument("--out")
    ms=sp.add_parser("forecast-scan"); ms.add_argument("--input",required=True); ms.add_argument("--top",type=int,default=5); ms.add_argument("--horizon",type=int,default=60); ms.add_argument("--max-rows",type=int,default=800); ms.add_argument("--out")
    sr=sp.add_parser("shadow-report"); sr.add_argument("--journal",required=True)
    z=sp.add_parser("live-all"); z.add_argument("--exchanges",default=",".join(EXCHANGES)); z.add_argument("--symbols",default=",".join(DEFAULT_SYMBOLS)); z.add_argument("--interval",type=int,default=30); z.add_argument("--cycles",type=int,default=0); z.add_argument("--fomo-chain",default="solana"); z.add_argument("--fomo-limit",type=int,default=5); z.add_argument("--project60-file",default=""); z.add_argument("--fomo-fills-file",default=""); z.add_argument("--fomo-leader-scores",default=""); z.add_argument("--outcome-journal",default="")
    x=ap.parse_args()
    if x.cmd=="demo": demo(x.out)
    elif x.cmd=="shadow-report": print(json.dumps(summarize_performance(x.journal),indent=2,ensure_ascii=False))
    elif x.cmd=="analyze": analyze(x.input,x.out)
    elif x.cmd=="real": real(x.symbol,x.interval,x.bars,x.out,x.report)
    elif x.cmd=="live": live(x.exchanges,x.symbols,x.interval,x.cycles)
    elif x.cmd=="intelligence": intelligence(x.input,x.out,x.pretty)
    elif x.cmd=="forecast-scan":
        result=scan_project60(x.input,top_n=x.top,max_rows=x.max_rows,horizon=x.horizon)
        write_report(result,x.out or Path(x.input).with_suffix(".forecast_scan.json"),{"mode":"Project60 multi-asset shortlist + validated forecast","top_n":x.top,"horizon_bars":x.horizon,"research_only":True,"live_orders":False})
        print("EARLY_OPPORTUNITY_WATCH count=" + str(result.get("early_watch_count", 0)))
    elif x.cmd=="forecast-project60":
        bars=load_project60_bars(x.input,x.asset,x.max_rows)
        result=walk_forward_forecast(bars,horizon=x.horizon,train_window=min(300,max(60,len(bars)-x.horizon-1)))
        economic_result=_non_overlapping_result(result,x.horizon)
        result["metrics"]=score_predictions(result)
        result["overlapping_forecast_diagnostic"]=diagnose_economic_edge(result)
        result["economic_edge"]=diagnose_economic_edge(economic_result)
        result["economic_metrics"]=_directional_metrics(economic_result,capital_usd=500.0,round_trip_cost_pct=0.35)
        result["capital_metrics"]=score_capital_targets(economic_result,capital_usd=500.0,min_profit_usd=4.0,preferred_profit_usd=10.0)
        result["acceptance_gate"]=forecast_acceptance_gate(result["metrics"],result["capital_metrics"])
        result["forecast_gate_passed"]=bool(result["acceptance_gate"].get("accepted"))
        result["trade_ready"]=False
        result["trade_readiness_reason"]="requires_actual_clock_execution_validation_with_ordered_costs_and_TP_SL"
        result["forecast_now"] = _validated_forecast_from_project60(x.input,x.asset,x.max_rows)
        write_report(result,x.out or Path(x.input).with_suffix(".forecast_project60.json"),{"mode":"Project60 walk-forward OOS","asset":x.asset,"bars":len(bars),"capital_usd":500.0,"min_profit_usd":4.0,"preferred_profit_usd":10.0,"research_only":True,"live_orders":False})
    elif x.cmd=="forecast-validate":
        bars=load_input(x.input)
        result=walk_forward_forecast(bars,horizon=x.horizon,train_window=x.train_window,fit_every=10)
        economic_result=_non_overlapping_result(result,x.horizon)
        result["metrics"]=score_predictions(result)
        result["overlapping_forecast_diagnostic"]=diagnose_economic_edge(result)
        result["economic_edge"]=diagnose_economic_edge(economic_result)
        result["economic_metrics"]=_directional_metrics(economic_result,capital_usd=500.0,round_trip_cost_pct=0.35)
        result["capital_metrics"]=score_capital_targets(economic_result,capital_usd=500.0,min_profit_usd=4.0,preferred_profit_usd=10.0)
        result["acceptance_gate"]=forecast_acceptance_gate(result["metrics"],result["capital_metrics"])
        result["forecast_gate_passed"]=bool(result["acceptance_gate"].get("accepted"))
        result["trade_ready"]=False
        result["trade_readiness_reason"]="requires_actual_clock_execution_validation_with_ordered_costs_and_TP_SL"
        write_report(result,x.out or Path(x.input).with_suffix(".forecast_validation.json"),{"mode":"walk-forward-OOS","capital_usd":500.0,"min_profit_usd":4.0,"preferred_profit_usd":10.0,"research_only":True,"live_orders":False})
    elif x.cmd=="live-all":
        if x.interval<10: raise ValueError("interval must be at least 10 seconds")
        count=0
        while x.cycles==0 or count<x.cycles:
            p60=summarize_project60(x.project60_file) if x.project60_file else None
            lf=summarize_fomo_leader_follower(x.fomo_fills_file,x.fomo_leader_scores) if x.fomo_fills_file else None
            outcome=summarize_paper_journal(x.outcome_journal) if x.outcome_journal else None
            forecast=_path_forecast_from_project60(x.project60_file, "BTC") if x.project60_file else None
            candle=analyze_candle_brain(x.project60_file, "BTC", max_rows=800, candle_span=5, lookback=200) if x.project60_file else None
            market_context=None
            if x.project60_file:
                try:
                    context_series=load_project60_assets(x.project60_file, max_rows=120)
                    market_context=analyze_market_context(context_series, reference="BTC", window=120)
                except Exception:
                    market_context={"available":False,"reason":"context_error","research_only":True,"live_orders":False}
            snap=run_live_brain(x.symbols.split(","),x.exchanges.split(","),x.fomo_chain,x.fomo_limit,p60,lf,outcome,forecast,candle,market_context)
            if x.outcome_journal:
                fc=snap.get("evidence",{}).get("forecast",{})
                selected=fc.get("selected") if isinstance(fc,dict) else {}
                current_price=selected.get("current_price") if isinstance(selected,dict) else None
                current_prices={}
                if x.project60_file:
                    try:
                        latest=Path(x.project60_file).read_text(encoding="utf-8").splitlines()[-1]
                        payload=json.loads(latest)
                        coins=payload.get("coins",{})
                        if isinstance(coins,list):
                            coins={str(v.get("coin")):v for v in coins if isinstance(v,dict)}
                        for asset,row in coins.items():
                            if isinstance(row,dict) and row.get("price") is not None:
                                price=float(row.get("price"))
                                if price>0:
                                    current_prices[str(asset).upper()]=price
                    except (OSError,ValueError,TypeError,IndexError,json.JSONDecodeError):
                        current_prices={}
                if current_prices:
                    resolve_open_signals(x.outcome_journal, current_prices)
                elif current_price is not None:
                    resolve_open_signals(x.outcome_journal, float(current_price))
            shadow_added=_append_shadow_if_actionable(x.outcome_journal,snap)
            shadow_metrics=summarize_performance(x.outcome_journal) if x.outcome_journal else None
            print_live_brain(snap)
            print(render_persian(snap,p60))
            if shadow_added:
                print("SHADOW_JOURNAL=APPENDED")
            if shadow_metrics is not None:
                print(format_performance_line(shadow_metrics))
            count+=1
            if x.cycles==0 or count<x.cycles: time.sleep(x.interval)
    else: dashboard(x.report,x.out)

if __name__=="__main__": main()
