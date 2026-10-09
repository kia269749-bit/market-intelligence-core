"""Train-selected ATR exit-policy tournament. Research only; never places orders."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from mi_core.adaptive_selector import STRATEGIES, _metrics, _signal
from mi_core.models import MarketBar

POLICIES = (
    ("atr_1p0_1p5", 1.0, 1.5),
    ("atr_1p5_2p0", 1.5, 2.0),
    ("atr_2p0_3p0", 2.0, 3.0),
)


def _atr(bars, i, period=14):
    start = max(1, i - period + 1)
    values = []
    for j in range(start, i + 1):
        high = float(bars[j].high if bars[j].high is not None else bars[j].price)
        low = float(bars[j].low if bars[j].low is not None else bars[j].price)
        prev = float(bars[j - 1].price)
        values.append(max(high - low, abs(high - prev), abs(low - prev)))
    return sum(values) / len(values) if values else 0.0


def _trade(bars, i, direction, horizon, cost_pct, stop_atr, target_atr):
    entry_i = i + 1
    if entry_i >= len(bars):
        return None
    entry_bar = bars[entry_i]
    entry = float(entry_bar.open if entry_bar.open is not None and entry_bar.open > 0 else entry_bar.price)
    atr = _atr(bars, i)
    if not math.isfinite(entry) or entry <= 0 or atr <= 0:
        return None
    stop = entry - direction * stop_atr * atr
    target = entry + direction * target_atr * atr
    last_i = min(len(bars) - 1, i + horizon + 1)
    exit_price = None
    exit_i = last_i
    reason = "time"
    for j in range(entry_i, last_i + 1):
        bar = bars[j]
        op = float(bar.open if bar.open is not None and bar.open > 0 else bar.price)
        hi = float(bar.high if bar.high is not None else bar.price)
        lo = float(bar.low if bar.low is not None else bar.price)
        if direction > 0:
            if op <= stop:
                exit_price, exit_i, reason = op, j, "stop_gap"
            elif op >= target:
                exit_price, exit_i, reason = target, j, "target_gap"
            elif lo <= stop and hi >= target:
                exit_price, exit_i, reason = stop, j, "both_stop_first"
            elif lo <= stop:
                exit_price, exit_i, reason = stop, j, "stop"
            elif hi >= target:
                exit_price, exit_i, reason = target, j, "target"
        else:
            if op >= stop:
                exit_price, exit_i, reason = op, j, "stop_gap"
            elif op <= target:
                exit_price, exit_i, reason = target, j, "target_gap"
            elif hi >= stop and lo <= target:
                exit_price, exit_i, reason = stop, j, "both_stop_first"
            elif hi >= stop:
                exit_price, exit_i, reason = stop, j, "stop"
            elif lo <= target:
                exit_price, exit_i, reason = target, j, "target"
        if exit_price is not None:
            break
    if exit_price is None:
        exit_price = float(bars[last_i].price)
    if not math.isfinite(exit_price) or exit_price <= 0:
        return None
    net = direction * (exit_price / entry - 1.0) * 100.0 - float(cost_pct)
    return {"index": i, "exit_index": exit_i, "net_pct": net, "reason": reason}


def _evaluate(bars, signals, strategy, horizon, cost_pct, stop_atr, target_atr, start, end):
    rows = []
    next_allowed = start
    for i in range(start, max(start, end - horizon - 1)):
        direction = signals[strategy][i]
        if not direction or i < next_allowed:
            continue
        result = _trade(bars, i, direction, horizon, cost_pct, stop_atr, target_atr)
        if result is None:
            continue
        rows.append(result)
        next_allowed = result["exit_index"] + 1
    metrics = _metrics([r["net_pct"] for r in rows])
    return metrics, rows


def evaluate(bars, horizon=24, cost_pct=0.35, holdout_bars=1000, min_train_trades=20):
    n = len(bars)
    if horizon < 1 or cost_pct < 0 or holdout_bars < horizon * 4:
        raise ValueError("invalid horizon, cost_pct, or holdout_bars")
    split = max(60, n - holdout_bars)
    signals = {name: [_signal(bars, i, name) for i in range(n)] for name in STRATEGIES}
    train, holdout = {}, {}
    for strategy in STRATEGIES:
        for policy, stop_atr, target_atr in POLICIES:
            key = f"{strategy}__{policy}"
            tm, _ = _evaluate(bars, signals, strategy, horizon, cost_pct, stop_atr, target_atr, 60, split)
            hm, rows = _evaluate(bars, signals, strategy, horizon, cost_pct, stop_atr, target_atr, split, n)
            train[key] = tm
            holdout[key] = {**hm, "stop_atr": stop_atr, "target_atr": target_atr}
    ranked = sorted(train, key=lambda k: (
        train[k]["trades"] >= min_train_trades,
        train[k]["ci_lower_pct"],
        train[k]["mean_net_pct"],
        train[k]["profit_factor"],
    ), reverse=True)
    selected = [
        k for k in ranked
        if train[k]["trades"] >= min_train_trades
        and train[k]["mean_net_pct"] > 0
        and train[k]["profit_factor"] >= 1.15
        and train[k]["ci_lower_pct"] > 0
        and train[k]["recent_mean_net_pct"] > 0
    ][:3]
    return {
        "symbol": bars[-1].symbol if bars else None, "samples": n,
        "train_bars": max(0, split - 60), "holdout_bars": n - split,
        "horizon_bars": horizon, "round_trip_cost_pct": cost_pct,
        "selected_on_training_only": selected,
        "selected_holdout_results": {k: holdout[k] for k in selected},
        "training_metrics": train,
        "holdout_metrics_all_families_exploratory": holdout,
        "selection_rule": "min trades, positive mean, PF>=1.15, positive 95% normal CI lower bound, positive recent mean; selection only on training",
        "same_bar_stop_target_rule": "if both touched, stop first (conservative)",
        "research_only": True, "live_orders": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--horizon", type=int, default=24)
    p.add_argument("--cost-pct", type=float, default=0.35)
    p.add_argument("--holdout-bars", type=int, default=1000)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    bars = [MarketBar(**json.loads(line)) for line in Path(a.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    result = evaluate(bars, a.horizon, a.cost_pct, a.holdout_bars)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "symbol": result["symbol"], "horizon_bars": result["horizon_bars"],
        "cost_pct": result["round_trip_cost_pct"],
        "selected_on_training_only": [
            {"strategy_policy": k, "train_trades": result["training_metrics"][k]["trades"],
             "train_mean_net_pct": result["training_metrics"][k]["mean_net_pct"],
             "train_pf": result["training_metrics"][k]["profit_factor"],
             "oos_trades": result["selected_holdout_results"][k]["trades"],
             "oos_mean_net_pct": result["selected_holdout_results"][k]["mean_net_pct"],
             "oos_net_profit_pct": result["selected_holdout_results"][k]["net_profit_pct"],
             "oos_pf": result["selected_holdout_results"][k]["profit_factor"]}
            for k in result["selected_on_training_only"]
        ],
        "research_only": True, "live_orders": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
