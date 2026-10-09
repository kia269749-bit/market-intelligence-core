"""Fixed combined-strategy tournament with cost sensitivity. Research only."""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from mi_core.storage import load_bars
from tools.external_strategy_tournament import _evaluate, _float_series, build_signals
from tools.regime_strategy_analysis import classify_regimes

DEFAULT_COSTS = (0.20, 0.25, 0.35)

def build_combined_signals(rows):
    base = build_signals(rows)
    regimes = classify_regimes(rows)
    n = len(rows)
    consensus, adaptive = [0.0] * n, [0.0] * n
    for i in range(n):
        ema, sma = base["ema20_50_trend"][i], base["sma200_trend_filter"][i]
        don, rsi = base["donchian20_10_breakout"][i], base["rsi14_mean_reversion"][i]
        consensus[i] = 1.0 if 2 * ema + sma + don + rsi >= 3 else 0.0
        regime = regimes[i]
        if regime.startswith("trend_up_"):
            adaptive[i] = 1.0 if ema + sma + don >= 2 else 0.0
        elif regime == "mixed_high_vol":
            adaptive[i] = 1.0 if don == 1.0 and (ema == 1.0 or sma == 1.0) else 0.0
        elif regime == "mixed_low_vol":
            adaptive[i] = 1.0 if rsi == 1.0 or (ema == 1.0 and sma == 1.0) else 0.0
        else:
            adaptive[i] = 0.0
    return {**base, "blend_weighted_consensus": consensus, "blend_regime_adaptive": adaptive}

def evaluate_cost_matrix(bars, *, costs=DEFAULT_COSTS, capital_usd=500.0):
    rows = sorted(bars, key=lambda b: int(b.ts))
    if len(rows) < 700:
        return {"status":"insufficient_data","bars":len(rows),"required_bars":700,
                "research_only":True,"live_orders":False,"trade_ready":False}
    timestamps = [int(b.ts) for b in rows]
    if any(b <= a for a,b in zip(timestamps,timestamps[1:])):
        raise ValueError("Timestamps must be strictly increasing.")
    for row in rows:
        o,h,l,c = (_float_series([row], key)[0] for key in ("open","high","low","price"))
        if not all(math.isfinite(x) for x in (o,h,l,c)) or h < max(o,c,l) or l > min(o,c,h):
            raise ValueError("Valid OHLC bars are required.")
    signals = build_combined_signals(rows)
    common_start = 200
    split_index = common_start + int((len(rows)-common_start)*0.70)
    results_by_cost = {}
    for cost in costs:
        cost = float(cost)
        if not math.isfinite(cost) or cost < 0 or cost > 5:
            raise ValueError("Cost percentages must be between 0 and 5.")
        key = format(cost, ".2f") + "%"
        results_by_cost[key] = {
            name: _evaluate(rows, signal, cost, capital_usd, common_start, split_index)
            for name,signal in signals.items()
        }
    summary = {}
    for name in ("blend_weighted_consensus","blend_regime_adaptive"):
        summary[name] = []
        for key,results in results_by_cost.items():
            oos = results[name]["holdout_oos"]
            summary[name].append({
                "cost_round_trip_pct":key,"net_profit_usd":oos["net_profit_usd"],
                "ending_equity_usd":oos["ending_equity_usd"],
                "max_drawdown_pct":oos["max_drawdown_pct"],
                "bar_profit_factor":oos["bar_profit_factor"],
                "position_changes":oos["position_changes"],"exposure_pct":oos["exposure_pct"]})
    return {
        "status":"ok","symbol":rows[-1].symbol,"interval":"1d","bars":len(rows),
        "capital_usd":float(capital_usd),"development_fraction":0.70,
        "holdout_start_ts":int(rows[split_index].ts),
        "execution":"completed-close signal, next-open execution, independent flat-start OOS",
        "cost_model":{
            "round_trip_cost_pct_scenarios":[float(x) for x in costs],
            "baseline_reference":"Binance regular-user spot fee 0.10% per side; 0.20% round trip before spread/slippage",
            "0.25%_scenario":"0.20% base fee plus 0.05% combined spread/slippage assumption",
            "0.35%_scenario":"conservative sensitivity case, not a claimed exchange fee",
            "limitations":"Daily OHLC cannot recover historical bid-ask spread or realized slippage; funding, taxes, outages and partial fills are excluded."},
        "strategy_definitions":{
            "blend_weighted_consensus":"2*EMA20/50 + SMA200 + Donchian20/10 + RSI14; long if score >= 3",
            "blend_regime_adaptive":"Uptrend: >=2 of EMA/SMA/Donchian; mixed high-vol: Donchian plus EMA or SMA; mixed low-vol: RSI or EMA+SMA; downtrend/unclassified: flat"},
        "results_by_cost":results_by_cost,"combined_strategy_summary":summary,
        "selection_policy":"No parameter fitting. Compare fixed blends with component baselines at same costs and chronological holdout. Do not select from one holdout alone.",
        "research_only":True,"live_orders":False,"trade_ready":False,
        "warning":"Positive holdout results are preliminary; require multiple untouched windows and paper-shadow evidence before production use."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",required=True); p.add_argument("--out",required=True)
    p.add_argument("--capital",type=float,default=500.0)
    p.add_argument("--costs",default="0.20,0.25,0.35")
    a=p.parse_args()
    costs=tuple(float(x.strip()) for x in a.costs.split(",") if x.strip())
    result=evaluate_cost_matrix(load_bars(a.input),costs=costs,capital_usd=a.capital)
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps({"symbol":result.get("symbol"),"status":result.get("status"),
        "combined_strategy_summary":result.get("combined_strategy_summary"),
        "research_only":result.get("research_only"),"trade_ready":result.get("trade_ready")},sort_keys=True))
if __name__=="__main__": main()
