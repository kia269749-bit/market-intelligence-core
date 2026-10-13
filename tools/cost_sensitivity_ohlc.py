"""Cost-sensitivity report for real-OHLC execution backtests.

Runs the expensive forecast/backtest once at zero modeled cost, then applies
explicit round-trip cost scenarios to the same realized gross trade paths.
Research only; this never places orders.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Direct execution (`python tools/cost_sensitivity_ohlc.py`) puts `tools/`,
# not the repository root, on sys.path. Add the root so package imports work
# both in GitHub Actions and when invoked directly from the repository.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.storage import load_bars
from tools.ohlc_execution_backtest import backtest


def metrics(trades, cost_pct, capital):
    equity = float(capital)
    peak = equity
    max_dd = 0.0
    wins = 0.0
    losses = 0.0
    win_count = 0
    for trade in trades:
        net_pct = float(trade["gross_return_pct"]) - cost_pct
        pnl = equity * net_pct / 100.0
        if pnl > 0:
            wins += pnl
            win_count += 1
        elif pnl < 0:
            losses += -pnl
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    count = len(trades)
    net = equity - capital
    return {
        "trades": count,
        "win_rate": round(win_count / count, 4) if count else 0.0,
        "net_profit_usd": round(net, 4),
        "return_pct": round(net / capital * 100.0, 4) if capital else 0.0,
        "expectancy_usd": round(net / count, 4) if count else 0.0,
        "profit_factor": round(wins / losses, 4) if losses else ("infinite" if wins else None),
        "max_drawdown_pct": round(max_dd, 4),
        "ending_equity_usd": round(equity, 4),
    }


def run(input_path, costs, output_path, capital=500.0):
    bars = load_bars(Path(input_path))
    base = backtest(bars, cost_pct=0.0, starting_capital=capital)
    if base.get("status") != "ok":
        report = {
            "status": base.get("status", "error"),
            "reason": base.get("reason", "backtest could not run"),
            "research_only": True,
            "live_orders": False,
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return report

    holdout_ts = int(base["holdout_start_ts"])
    scenarios = []
    for cost in costs:
        configurations = []
        for row in base["results"]:
            development, holdout = [], []
            purged = 0
            for trade in row["trades"]:
                signal_ts = int(trade["signal_ts"])
                exit_ts = int(trade["exit_ts"])
                if signal_ts >= holdout_ts:
                    holdout.append(trade)
                elif exit_ts < holdout_ts:
                    development.append(trade)
                else:
                    purged += 1
            configurations.append({
                "target_pct": row["target_pct"],
                "stop_pct": row["stop_pct"],
                "cohort": row["cohort"],
                "development": metrics(development, cost, capital),
                "untouched_holdout_oos": metrics(holdout, cost, capital),
                "purged_boundary_trades": purged,
            })
        scenarios.append({
            "round_trip_cost_pct": cost,
            "configurations": configurations,
        })

    report = {
        "status": "ok",
        "symbol": bars[-1].symbol,
        "bars": len(bars),
        "evaluation_points": base["evaluation_points"],
        "raw_candidate_indices": base.get("raw_candidate_indices"),
        "holdout_start_ts": holdout_ts,
        "capital_usd": capital,
        "cost_scenarios": scenarios,
        "method": "one shared gross-trade path; fixed round-trip cost subtracted from each trade return; development boundary-crossing trades purged; final chronological holdout kept separate",
        "limitations": [
            "Cost sensitivity is conditional on the same forecast directions and trade paths; it does not reselect strategies per cost.",
            "Fixed cost percentages are assumptions, not exchange-specific fee or slippage measurements.",
            "The output is not a mark-to-market portfolio simulation and does not prove future profitability.",
        ],
        "research_only": True,
        "live_orders": False,
        "trade_ready": False,
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    brief = []
    for scenario in scenarios:
        cost = scenario["round_trip_cost_pct"]
        rows = scenario["configurations"]
        holdout_returns = [x["untouched_holdout_oos"]["return_pct"] for x in rows if x["untouched_holdout_oos"]["trades"]]
        brief.append({
            "cost_pct": cost,
            "configurations": len(rows),
            "profitable_holdout_configurations": sum(x["untouched_holdout_oos"]["net_profit_usd"] > 0 for x in rows),
            "holdout_return_pct_median": round(sorted(holdout_returns)[len(holdout_returns)//2], 4) if holdout_returns else None,
        })
    print(json.dumps({
        "status": report["status"], "symbol": report["symbol"],
        "research_only": True, "live_orders": False,
        "cost_sensitivity_summary": brief,
    }, sort_keys=True))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--costs", default="0,0.05,0.10,0.20,0.35",
                        help="comma-separated round-trip cost percentages")
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    costs = [float(value) for value in args.costs.split(",")]
    if not costs or any(value < 0 for value in costs):
        parser.error("costs must be non-negative percentages")
    run(args.input, costs, args.out, args.capital)


if __name__ == "__main__":
    main()
