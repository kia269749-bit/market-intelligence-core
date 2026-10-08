"""Run a lightweight, leakage-safe OOS evaluation of the 5/10/20/50-bar path forecast.

Research only. Reads an append-only Project 60 JSONL file and never modifies it.
The forecast at time t only sees rows <= t; realized returns use t+h.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from mi_core.models import MarketBar
from mi_core.path_forecast import HORIZONS, forecast_path, path_to_economic_opportunity


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_project60(path: str, symbols: set[str], max_rows: int) -> dict[str, list[MarketBar]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    raw = []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                raw.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if max_rows > 0:
        raw = raw[-max_rows:]

    out = {s: [] for s in symbols}
    for rec in raw:
        ts = rec.get("timestamp", rec.get("ts", 0))
        if isinstance(ts, str):
            try:
                ts = int(float(ts))
            except ValueError:
                ts = len(out[next(iter(out))])
        coins = rec.get("coins") or {}
        for wanted in symbols:
            asset = None
            for key, value in coins.items():
                if str(key).upper() == wanted or str((value or {}).get("coin", key)).upper() == wanted:
                    asset = value
                    break
            if not isinstance(asset, dict) or "error" in asset:
                continue
            price = _num(asset.get("price"))
            if price <= 0:
                continue
            trades = asset.get("trades") or {}
            out[wanted].append(
                MarketBar(
                    ts=int(ts),
                    symbol=wanted,
                    price=price,
                    volume=_num(asset.get("volume")),
                    oi=asset.get("open_interest"),
                    funding=asset.get("funding"),
                    buy_volume=_num(trades.get("buy_usd")),
                    sell_volume=_num(trades.get("sell_usd")),
                )
            )
    for bars in out.values():
        bars.sort(key=lambda b: b.ts)
    return out


def _metrics(rows, capital):
    pnls = [r["net_pnl_usd"] for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = capital
    peak = capital
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
    return {
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "net_profit_usd": sum(pnls),
        "expectancy_usd": sum(pnls) / len(pnls) if pnls else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss else (None if gross_profit else 0.0),
        "max_drawdown": max_dd,
        "avg_realized_directional_move_pct": (
            sum(r["directional_move_pct"] for r in rows) / len(rows) if rows else 0.0
        ),
    }


def _directional_metrics(rows):
    forecasts = [r for r in rows if r["direction"] in ("UP", "DOWN")]
    correct = [r for r in forecasts if r["directional_move_pct"] > 0]
    up = [r for r in forecasts if r["direction"] == "UP"]
    down = [r for r in forecasts if r["direction"] == "DOWN"]
    flat = [r for r in rows if r["direction"] == "FLAT"]
    return {
        "forecast_points": len(rows),
        "directional_forecasts": len(forecasts),
        "flat_forecasts": len(flat),
        "up_forecasts": len(up),
        "down_forecasts": len(down),
        "direction_correct": len(correct),
        "direction_accuracy": len(correct) / len(forecasts) if forecasts else 0.0,
        "avg_directional_move_pct": (
            sum(r["directional_move_pct"] for r in forecasts) / len(forecasts)
            if forecasts else 0.0
        ),
    }


def _tier_metrics(rows):
    counts = {}
    for r in rows:
        tier = r["tier"]
        counts[tier] = counts.get(tier, 0) + 1
    return counts


def _reject_reason_metrics(rows):
    counts = {}
    for r in rows:
        reason = r.get("reject_reason") or ""
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def evaluate(bars, *, capital, cost_pct, step, min_history, max_eval):
    results = {h: {"all_forecasts": [], "viable": []} for h in HORIZONS}
    start = max(min_history - 1, 0)
    end = min(len(bars) - max(HORIZONS) - 1, start + max_eval) if max_eval > 0 else len(bars) - max(HORIZONS) - 1
    for i in range(start, max(start, end) + 1, max(1, step)):
        history = bars[: i + 1]
        path = forecast_path(history, min_history=min_history)
        if path is None:
            continue
        econ = path_to_economic_opportunity(path, round_trip_cost_pct=cost_pct)
        by_h = {x["horizon"]: x for x in econ["horizons"]}
        for h in HORIZONS:
            f = by_h[h]
            j = i + h
            if j >= len(bars):
                continue
            realized = math.log(bars[j].price / bars[i].price) * 100.0
            direction = f["direction"]
            directional = (
                realized if direction == "UP"
                else -realized if direction == "DOWN"
                else 0.0
            )
            net_pnl = capital * (directional - cost_pct) / 100.0
            row = {
                "ts": bars[i].ts,
                "horizon": h,
                "direction": direction,
                "expected_return_pct": f["expected_return_pct"],
                "target_hit_probability": f["target_hit_probability"],
                "selected_target_pct": f.get("selected_target_pct", 0.0),
                "selected_target_hit_probability": f.get("selected_target_hit_probability", 0.0),
                "target_ladder_probability": f.get("target_ladder_probability", {}),
                "reject_reason": f.get("reject_reason", ""),
                "tier": f["tier"],
                "realized_return_pct": realized,
                "directional_move_pct": directional,
                "net_pnl_usd": net_pnl,
            }
            results[h]["all_forecasts"].append(row)
            if f["tier"] in ("VIABLE", "STRONG"):
                results[h]["viable"].append(row)

    return {
        str(h): {
            "directional_metrics": _directional_metrics(v["all_forecasts"]),
            "tier_counts": _tier_metrics(v["all_forecasts"]),
            "reject_reason_counts": _reject_reason_metrics(v["all_forecasts"]),
            "rejection_diagnostics": {
                "total_rejected": sum(_reject_reason_metrics(v["all_forecasts"]).values()),
                "reason_counts": _reject_reason_metrics(v["all_forecasts"]),
            },
            "economic_metrics": _metrics(v["viable"], capital),
            "forecast_count": len(v["all_forecasts"]),
            "economic_trade_count": len(v["viable"]),
            "note": (
                "directional_metrics evaluate forecast direction only; "
                "economic_metrics include only VIABLE/STRONG setups after costs. "
                "No rejected forecast is counted as a trade."
            ),
        }
        for h, v in results.items()
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project60-file", required=True)
    ap.add_argument("--symbols", default="BTC,ETH")
    ap.add_argument("--capital", type=float, default=500.0)
    ap.add_argument("--cost-pct", type=float, default=0.0, help="Execution cost for economic stress tests; 0 = signal-quality mode.")
    ap.add_argument("--step", type=int, default=10, help="Evaluate every N Project-60 bars.")
    ap.add_argument("--min-history", type=int, default=140)
    ap.add_argument("--max-rows", type=int, default=0, help="0 = all rows")
    ap.add_argument("--max-eval", type=int, default=0, help="0 = all eligible evaluation points")
    args = ap.parse_args()

    symbols = {x.strip().upper() for x in args.symbols.split(",") if x.strip()}
    data = load_project60(args.project60_file, symbols, args.max_rows)
    report = {
        "research_only": True,
        "live_orders": False,
        "reporting_capital_usd": args.capital,
        "round_trip_cost_pct": args.cost_pct,
        "step_bars": args.step,
        "min_history": args.min_history,
        "horizons": list(HORIZONS),
        "diagnostics_version": "reject-reasons-v4-capital-independent-edge",
        "assets": {},
    }

    for symbol, bars in data.items():
        if len(bars) > 1:
            deltas = [bars[i].ts - bars[i-1].ts for i in range(1, len(bars))]
            report.setdefault("sampling", {})[symbol] = {
                "median_seconds": sorted(deltas)[len(deltas)//2],
                "mean_seconds": sum(deltas) / len(deltas),
                "min_seconds": min(deltas),
                "max_seconds": max(deltas),
                "horizons_are_bars_not_minutes": True,
            }
        if len(bars) < args.min_history + max(HORIZONS):
            report["assets"][symbol] = {"status": "insufficient_data", "bars": len(bars)}
            continue
        evaluated = evaluate(
            bars,
            capital=args.capital,
            cost_pct=args.cost_pct,
            step=args.step,
            min_history=args.min_history,
            max_eval=args.max_eval,
        )
        report["assets"][symbol] = {
            "status": "ok",
            "bars": len(bars),
            "start_ts": bars[0].ts,
            "end_ts": bars[-1].ts,
            "evaluation": evaluated,
        }

    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
