"""Research-only strategy tournament with TP ladder and close-based stop simulation.

Uses only historical Project60 MarketBar fields. Since current snapshots expose
prices rather than candle highs/lows, target/stop touches are inferred from
snapshot closes and explicitly labelled approximate. No orders are sent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .multi_asset_forecast import load_project60_assets

TP_LEVELS = (1.15, 1.75, 2.35)
DEFAULT_STOP_PCT = 0.75
STRATEGIES = ("trend", "flow", "two_of_three", "unanimous")


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0 if b > 0 else 0.0


def _sign(value: float, threshold: float = 0.0) -> int:
    return 1 if value > threshold else -1 if value < -threshold else 0


def engine_votes(bars, i: int) -> dict[str, int]:
    """Build causal, lightweight votes from data available at index i only."""
    if i < 60:
        return {"trend": 0, "flow": 0, "trade_flow": 0}
    prices = [float(bars[j].price) for j in range(i - 60, i + 1)]
    r5 = _pct(prices[-1], prices[-6])
    r15 = _pct(prices[-1], prices[-16])
    r60 = _pct(prices[-1], prices[0])
    # Trend vote requires short and medium momentum agreement; 60-bar move
    # confirms context but does not veto a valid pullback continuation.
    trend = _sign(0.55 * r5 + 0.30 * r15 + 0.15 * r60, 0.035)
    recent = bars[i - 4:i + 1]
    flow_num = sum(float(b.buy_volume or 0) - float(b.sell_volume or 0) for b in recent)
    flow_den = sum(float(b.buy_volume or 0) + float(b.sell_volume or 0) for b in recent)
    trade_imbalance = flow_num / flow_den if flow_den > 0 else 0.0
    b = bars[i]
    bid = float(b.bid or 0)
    ask = float(b.ask or 0)
    book_imbalance = (bid - ask) / (bid + ask) if bid + ask > 0 else 0.0
    oi_delta = 0.0
    prev = bars[i - 5]
    if b.oi not in (None, 0) and prev.oi not in (None, 0):
        oi_delta = float(b.oi) / float(prev.oi) - 1.0
    flow_score = 0.60 * trade_imbalance + 0.30 * book_imbalance + 0.10 * max(-1.0, min(1.0, oi_delta * 20))
    flow = _sign(flow_score, 0.035)
    # A separate price/volume-flow confirmation vote, not a claim to identify
    # a wallet or institutional owner.
    trade_flow = _sign(0.70 * trade_imbalance + 0.30 * _sign(r5) * min(1.0, abs(r5) / 0.2), 0.06)
    return {"trend": trend, "flow": flow, "trade_flow": trade_flow}


def strategy_signal(votes: dict[str, int], strategy: str) -> int:
    if strategy == "trend":
        return votes["trend"]
    if strategy == "flow":
        return votes["flow"]
    vals = [votes["trend"], votes["flow"], votes["trade_flow"]]
    if strategy == "two_of_three":
        bullish = sum(v == 1 for v in vals)
        bearish = sum(v == -1 for v in vals)
        return 1 if bullish >= 2 else -1 if bearish >= 2 else 0
    if strategy == "unanimous":
        return vals[0] if vals[0] != 0 and vals.count(vals[0]) == 3 else 0
    raise ValueError(f"unknown strategy: {strategy}")


def _simulate_segment(bars, start: int, end: int, strategy: str, horizon: int,
                      targets=TP_LEVELS, stop_pct=DEFAULT_STOP_PCT,
                      round_trip_cost_pct=0.35) -> dict[str, Any]:
    """One-position-at-a-time ledger; enter at next snapshot close, close-only path."""
    trades = []
    i = max(start, 60)
    end = min(end, len(bars) - 1)
    horizon = max(1, int(horizon))
    while i < end - horizon - 1:
        votes = engine_votes(bars, i)
        side = strategy_signal(votes, strategy)
        if side == 0:
            i += 1
            continue
        entry_i = i + 1
        entry = float(bars[entry_i].price)
        if entry <= 0:
            i += 1
            continue
        deadline = min(end, entry_i + int(horizon))
        remaining = 1.0
        realized_gross_pct = 0.0
        hit_levels = []
        exit_reason = "TIME"
        exit_i = deadline
        last_price = float(bars[deadline].price)
        for k in range(entry_i + 1, deadline + 1):
            px = float(bars[k].price)
            favorable = _pct(px, entry) * side
            adverse = -favorable
            # Close-only observation avoids inventing intrabar order. If a close
            # crosses several levels, fills are recorded at the predefined level.
            for level_index, target in enumerate(targets):
                if level_index + 1 not in hit_levels and favorable >= float(target):
                    slice_size = 1.0 / len(targets)
                    realized_gross_pct += slice_size * float(target)
                    remaining -= slice_size
                    hit_levels.append(level_index + 1)
                    exit_reason = f"TP{level_index + 1}" if remaining <= 1e-9 else exit_reason
            if adverse >= float(stop_pct) and remaining > 1e-9:
                realized_gross_pct += remaining * (-float(stop_pct))
                remaining = 0.0
                exit_reason = "STOP"
                exit_i = k
                break
            if remaining <= 1e-9:
                exit_reason = "TP3"
                exit_i = k
                break
            last_price = px
        if remaining > 1e-9:
            signed_return = _pct(last_price, entry) * side
            realized_gross_pct += remaining * signed_return
        net_pct = realized_gross_pct - float(round_trip_cost_pct)
        trades.append({
            "entry_index": entry_i, "exit_index": exit_i, "side": "BUY" if side == 1 else "SELL",
            "entry": entry, "exit": float(bars[exit_i].price),
            "tp_levels_hit": list(hit_levels), "max_tp": max(hit_levels, default=0),
            "exit_reason": exit_reason, "gross_return_pct": round(realized_gross_pct, 6),
            "net_return_pct": round(net_pct, 6), "win": net_pct > 0,
        })
        # Prevent overlapping trades and repeated counting of the same price path.
        i = max(i + 1, exit_i)
    n = len(trades)
    wins = sum(t["win"] for t in trades)
    gross_profit = sum(t["net_return_pct"] for t in trades if t["net_return_pct"] > 0)
    gross_loss = -sum(t["net_return_pct"] for t in trades if t["net_return_pct"] < 0)
    equity = peak = max_dd = 0.0
    for t in trades:
        equity += t["net_return_pct"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": n, "wins": wins, "losses": n - wins,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "tp1_count": sum(t["max_tp"] >= 1 for t in trades),
        "tp2_count": sum(t["max_tp"] >= 2 for t in trades),
        "tp3_count": sum(t["max_tp"] >= 3 for t in trades),
        "net_return_sum_pct": round(sum(t["net_return_pct"] for t in trades), 6),
        "expectancy_pct": round(sum(t["net_return_pct"] for t in trades) / n, 6) if n else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (None if gross_profit == 0 else "INF"),
        "max_drawdown_pct_points": round(max_dd, 6),
        "trade_ledger": trades,
    }


def run_tournament(path: str, max_rows: int = 800, horizons=(5, 15, 60),
                   targets=TP_LEVELS, stop_pct=DEFAULT_STOP_PCT,
                   round_trip_cost_pct=0.35, min_trades: int = 10) -> dict[str, Any]:
    series = load_project60_assets(path, max_rows=max_rows)
    all_results = []
    for symbol, bars in sorted(series.items()):
        if len(bars) < 180:
            all_results.append({"symbol": symbol, "status": "INSUFFICIENT_HISTORY", "samples": len(bars)})
            continue
        n = len(bars)
        train_end = int(n * 0.60)
        validation_end = int(n * 0.80)
        for horizon in horizons:
            candidates = []
            for strategy in STRATEGIES:
                validation = _simulate_segment(bars, train_end, validation_end, strategy, horizon,
                                                targets, stop_pct, round_trip_cost_pct)
                holdout = _simulate_segment(bars, validation_end, n - 1, strategy, horizon,
                                            targets, stop_pct, round_trip_cost_pct)
                candidates.append({"strategy": strategy, "validation": validation, "holdout": holdout})
            eligible = [x for x in candidates if x["validation"]["trades"] >= min_trades
                        and x["validation"]["net_return_sum_pct"] > 0]
            selected = max(eligible, key=lambda x: (x["validation"]["expectancy_pct"],
                                                     x["validation"]["net_return_sum_pct"])) if eligible else None
            chosen_holdout = selected["holdout"] if selected else None
            promoted = bool(selected and chosen_holdout and chosen_holdout["trades"] >= min_trades
                            and chosen_holdout["net_return_sum_pct"] > 0
                            and chosen_holdout["expectancy_pct"] > 0)
            all_results.append({
                "symbol": symbol, "samples": n, "horizon_minutes": int(horizon),
                "split": {"discovery_pct": 60, "selection_pct": 20, "locked_holdout_pct": 20},
                "candidates": candidates,
                "selected_on_validation": selected["strategy"] if selected else None,
                "selected_validation": selected["validation"] if selected else None,
                "selected_locked_holdout": chosen_holdout,
                "promotion_status": "SHADOW_CANDIDATE" if promoted else "NO_EDGE_PROVEN",
                "research_only": True, "live_orders": False,
            })
    return {
        "mode": "close_only_tp_ladder_strategy_tournament",
        "input": str(path), "max_rows_per_asset": int(max_rows),
        "horizons_minutes": [int(h) for h in horizons],
        "tp_levels_pct": [float(x) for x in targets], "stop_pct": float(stop_pct),
        "round_trip_cost_pct": float(round_trip_cost_pct), "min_trades_per_selection_segment": int(min_trades),
        "results": all_results,
        "limitations": [
            "Project60 input contains snapshots, not candle OHLC; TP/stop ordering uses observed closes only.",
            "The third vote is trade-flow confirmation, not wallet-level FOMO intelligence; wallet data is not currently wired into this loader.",
            "A positive selection segment is insufficient: the chosen strategy must also pass the untouched chronological holdout.",
            "These results are research-only and do not place or enable orders."
        ],
        "research_only": True, "live_orders": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research-only TP ladder strategy tournament")
    parser.add_argument("--input", required=True)
    parser.add_argument("--max-rows", type=int, default=800)
    parser.add_argument("--horizons", default="5,15,60")
    parser.add_argument("--targets", default="1.15,1.75,2.35")
    parser.add_argument("--stop", type=float, default=DEFAULT_STOP_PCT)
    parser.add_argument("--cost", type=float, default=0.35)
    parser.add_argument("--min-trades", type=int, default=10)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    horizons = tuple(int(x.strip()) for x in args.horizons.split(",") if x.strip())
    targets = tuple(float(x.strip()) for x in args.targets.split(",") if x.strip())
    if not horizons or any(h <= 0 for h in horizons):
        parser.error("--horizons must contain positive integers")
    if not targets or any(t <= 0 for t in targets) or tuple(sorted(targets)) != targets:
        parser.error("--targets must be positive and strictly increasing")
    if args.stop <= 0 or args.cost < 0 or args.max_rows <= 0 or args.min_trades <= 0:
        parser.error("--stop and --max-rows/--min-trades must be positive; --cost cannot be negative")
    result = run_tournament(args.input, args.max_rows, horizons, targets, args.stop, args.cost, args.min_trades)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
        print(out)
        for row in result["results"]:
            if "horizon_minutes" in row:
                print(json.dumps({k: row[k] for k in ("symbol", "horizon_minutes", "selected_on_validation", "promotion_status", "selected_validation", "selected_locked_holdout")}, ensure_ascii=False))
    else:
        print(payload)


if __name__ == "__main__":
    main()
