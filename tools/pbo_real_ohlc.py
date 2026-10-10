"""Real-OHLC CSCV/PBO diagnostic using the execution-aware backtest.

Research only. CSCV sees development-period, bar-aligned realized net returns.
The final chronological holdout is reported separately and is never used to
select strategies inside the PBO calculation. Returns are booked at exit bars;
non-exit bars have zero realized return (not mark-to-market returns).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.pbo import estimate_pbo_cscv
from mi_core.storage import load_bars
from tools.ohlc_execution_backtest import backtest


def _strategy_name(row: dict) -> str:
    return (
        f"target={row.get('target_pct')}|stop={row.get('stop_pct')}|"
        f"cohort={row.get('cohort', 'unknown')}"
    )


def _trade_metrics(trades: list[dict]) -> dict:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    positive = []
    negative = []
    for trade in sorted(trades, key=lambda t: (int(t["exit_ts"]), int(t["signal_ts"]))):
        ret = float(trade["net_return_pct"]) / 100.0
        equity *= 1.0 + ret
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
        (positive if ret > 0 else negative).append(ret)
    n = len(trades)
    gross_win = sum(positive)
    gross_loss = abs(sum(negative))
    return {
        "trades": n,
        "net_return_pct_compounded": round((equity - 1.0) * 100.0, 6),
        "mean_trade_net_pct": round(mean([float(t["net_return_pct"]) for t in trades]), 6) if n else 0.0,
        "win_rate": round(len(positive) / n, 6) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 6) if gross_loss else (None if not positive else "infinite"),
        "max_drawdown_pct": round(max_drawdown * 100.0, 6),
    }


def build_aligned_return_matrix(
    timestamps: list[int],
    result_rows: list[dict],
    holdout_start_ts: int,
    *,
    n_blocks: int = 8,
    min_development_trades: int = 5,
) -> dict:
    """Build per-bar net-return series and keep the chronological holdout separate."""
    if n_blocks < 4 or n_blocks % 2:
        raise ValueError("n_blocks must be an even integer >= 4")
    dev_timestamps = [int(ts) for ts in timestamps if int(ts) < int(holdout_start_ts)]
    used_n = len(dev_timestamps) - len(dev_timestamps) % n_blocks
    if used_n < n_blocks:
        raise ValueError("not enough development bars for the requested CSCV blocks")
    used_timestamps = dev_timestamps[:used_n]
    index_by_ts = {ts: i for i, ts in enumerate(used_timestamps)}
    matrix = {}
    candidates = []
    for row in result_rows:
        name = _strategy_name(row)
        if name in matrix:
            raise ValueError(f"duplicate strategy configuration: {name}")
        series = [0.0] * used_n
        development = []
        holdout = []
        purged = 0
        truncated = 0
        for trade in row.get("trades", []):
            signal_ts = int(trade["signal_ts"])
            exit_ts = int(trade["exit_ts"])
            if signal_ts >= holdout_start_ts:
                holdout.append(dict(trade))
            elif exit_ts >= holdout_start_ts:
                # Do not let a development entry consume an outcome from the holdout.
                purged += 1
            elif exit_ts not in index_by_ts:
                # The final incomplete CSCV block is omitted consistently for every strategy.
                truncated += 1
            else:
                development.append(dict(trade))
                series[index_by_ts[exit_ts]] += float(trade["net_return_pct"]) / 100.0
        eligible = len(development) >= min_development_trades
        candidates.append({
            "strategy": name,
            "eligible_for_pbo": eligible,
            "development_trades_used": len(development),
            "holdout_trades": len(holdout),
            "purged_boundary_trades": purged,
            "excluded_incomplete_tail_trades": truncated,
            "development_metrics": _trade_metrics(development),
            "untouched_holdout_metrics": _trade_metrics(holdout),
        })
        if eligible:
            matrix[name] = series
    return {
        "returns_by_strategy": matrix,
        "candidates": candidates,
        "development_bars_before_block_trim": len(dev_timestamps),
        "development_bars_used_for_pbo": used_n,
        "development_bars_trimmed_for_equal_blocks": len(dev_timestamps) - used_n,
        "holdout_start_ts": int(holdout_start_ts),
        "n_blocks": n_blocks,
        "min_development_trades": min_development_trades,
    }


def run_real_pbo(
    bars: list,
    *,
    n_blocks: int = 8,
    min_development_trades: int = 5,
    max_evals: int = 80,
    horizon_bars: int = 96,
    step_bars: int = 48,
    min_history: int = 300,
    cost_pct: float = 0.35,
) -> dict:
    base = backtest(
        bars,
        horizon_bars=horizon_bars,
        step_bars=step_bars,
        max_evals=max_evals,
        min_history=min_history,
        cost_pct=cost_pct,
    )
    if base.get("status") != "ok":
        return {
            "status": "unavailable",
            "reason": base.get("reason", base.get("status", "backtest_failed")),
            "research_only": True,
            "live_orders": False,
        }
    aligned = build_aligned_return_matrix(
        [int(bar.ts) for bar in bars],
        base["results"],
        int(base["holdout_start_ts"]),
        n_blocks=n_blocks,
        min_development_trades=min_development_trades,
    )
    report = {
        "status": "ok" if len(aligned["returns_by_strategy"]) >= 2 else "pbo_unavailable",
        "symbol": base.get("symbol"),
        "bars": base.get("bars"),
        "evaluation_points": base.get("evaluation_points"),
        "cost_round_trip_pct": cost_pct,
        "strategy_candidates_total": len(base["results"]),
        "strategy_candidates_eligible_for_pbo": len(aligned["returns_by_strategy"]),
        "pbo_method": "CSCV on aligned realized per-bar net returns during development only",
        "return_construction": "net trade return booked at exit bar; zero on bars without a realized exit; not mark-to-market",
        "pbo_input": {
            "n_blocks": n_blocks,
            "development_bars_used": aligned["development_bars_used_for_pbo"],
            "development_bars_trimmed_for_equal_blocks": aligned["development_bars_trimmed_for_equal_blocks"],
            "min_development_trades_per_strategy": min_development_trades,
        },
        "candidates": aligned["candidates"],
        "holdout_start_ts": aligned["holdout_start_ts"],
        "research_only": True,
        "live_orders": False,
        "limitations": [
            "PBO measures strategy-selection overfit among the eligible candidates; it does not prove future profitability.",
            "Returns are realized trade returns booked at exit bars, not a mark-to-market portfolio equity curve.",
            "The final chronological holdout is reported separately and is not used to calculate PBO.",
            "The fixed round-trip cost is a model assumption; validate fee, spread, slippage and funding sensitivity.",
            "This diagnostic does not authorize live orders or change any existing service.",
        ],
    }
    if len(aligned["returns_by_strategy"]) >= 2:
        report["pbo"] = estimate_pbo_cscv(aligned["returns_by_strategy"], n_blocks=n_blocks)
    else:
        report["reason"] = "fewer than two strategies met the minimum development-trade requirement"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSONL containing real OHLC bars")
    parser.add_argument("--out", required=True, help="Output JSON report")
    parser.add_argument("--blocks", type=int, default=8)
    parser.add_argument("--min-development-trades", type=int, default=5)
    parser.add_argument("--max-evals", type=int, default=80)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--step-bars", type=int, default=48)
    parser.add_argument("--min-history", type=int, default=300)
    parser.add_argument("--cost-pct", type=float, default=0.35)
    args = parser.parse_args()
    if not math.isfinite(args.cost_pct) or args.cost_pct < 0:
        parser.error("--cost-pct must be a finite non-negative percentage")
    bars = load_bars(Path(args.input))
    report = run_real_pbo(
        bars,
        n_blocks=args.blocks,
        min_development_trades=args.min_development_trades,
        max_evals=args.max_evals,
        horizon_bars=args.horizon_bars,
        step_bars=args.step_bars,
        min_history=args.min_history,
        cost_pct=args.cost_pct,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in {"candidates", "pbo"}}
    summary["candidates"] = report.get("candidates", [])
    if "pbo" in report:
        summary["pbo"] = {k: v for k, v in report["pbo"].items() if k != "split_results"}
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    return 0 if report.get("status") in {"ok", "pbo_unavailable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
