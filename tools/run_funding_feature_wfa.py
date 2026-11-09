#!/usr/bin/env python3
"""Technical Funding-feature runner and deterministic gate-statistics primitives.

The CLI remains a technical model smoke runner. The economic gate is never
started by this script unless a separately reviewed caller invokes the pure
calculation functions below.
"""
from __future__ import annotations
import argparse
import json
import math
import random
from pathlib import Path
from typing import Mapping, Sequence
from mi_core.models import MarketBar
from mi_core.validated_forecast import walk_forward_forecast

STRICT_ROUND_TRIP_COST_PCT = 0.45
BOOTSTRAP_BLOCK_DAYS = 5
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20261109
HOLM_HYPOTHESES = 2
ALPHA = 0.05


def calculate_portfolio_daily_net_returns(
    gross_returns_by_asset: Mapping[str, Sequence[float]],
    trades_by_asset: Mapping[str, Sequence[int]],
    strict_cost_pct: float = STRICT_ROUND_TRIP_COST_PCT,
) -> list[float]:
    """Equal-weight, unlevered daily portfolio returns in percentage points.

    An asset/day with no trade contributes exactly zero. Each completed
    round-trip trade deducts the strict cost once from that asset/day.
    """
    if not gross_returns_by_asset or set(gross_returns_by_asset) != set(trades_by_asset):
        raise ValueError("return and trade maps must contain the same non-empty assets")
    lengths = {len(v) for v in gross_returns_by_asset.values()} | {len(v) for v in trades_by_asset.values()}
    if len(lengths) != 1:
        raise ValueError("all asset series must have equal length")
    n = lengths.pop()
    if n == 0:
        return []
    assets = sorted(gross_returns_by_asset)
    out = []
    for day in range(n):
        daily = []
        for asset in assets:
            gross = float(gross_returns_by_asset[asset][day])
            trades = int(trades_by_asset[asset][day])
            if trades < 0:
                raise ValueError("trade counts cannot be negative")
            daily.append(gross - trades * strict_cost_pct if trades else 0.0)
        out.append(sum(daily) / len(assets))
    return out


def calculate_buy_and_hold_daily_returns(
    gross_returns_by_asset: Mapping[str, Sequence[float]],
    strict_cost_pct: float = STRICT_ROUND_TRIP_COST_PCT,
) -> list[float]:
    """Equal-weight buy-and-hold daily returns, charging one entry RT cost.

    The one-time 0.45% cost is deducted from each asset's first daily return;
    averaging those equally weighted asset returns charges the portfolio once.
    """
    if not gross_returns_by_asset:
        raise ValueError("at least one asset is required")
    lengths = {len(v) for v in gross_returns_by_asset.values()}
    if len(lengths) != 1:
        raise ValueError("all asset series must have equal length")
    n = lengths.pop()
    if n == 0:
        return []
    assets = sorted(gross_returns_by_asset)
    out = []
    for day in range(n):
        vals = []
        for asset in assets:
            value = float(gross_returns_by_asset[asset][day])
            if day == 0:
                value -= strict_cost_pct
            vals.append(value)
        out.append(sum(vals) / len(assets))
    return out


def maximum_drawdown_pct(daily_returns_pct: Sequence[float]) -> float:
    equity = peak = 1.0
    worst = 0.0
    for ret in daily_returns_pct:
        equity *= 1.0 + float(ret) / 100.0
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak * 100.0)
    return worst


def block_bootstrap_one_sided_pvalue(
    candidate_daily_returns_pct: Sequence[float],
    benchmark_daily_returns_pct: Sequence[float],
    block_days: int = BOOTSTRAP_BLOCK_DAYS,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> float:
    """Paired circular moving-block bootstrap p-value for candidate > benchmark.

    The paired daily difference is centered under H0. Circular contiguous
    blocks preserve short-run dependence. The one-sided tail is P(null mean
    >= observed mean); the plus-one correction prevents a zero p-value.
    """
    if len(candidate_daily_returns_pct) != len(benchmark_daily_returns_pct):
        raise ValueError("paired daily series must have equal lengths")
    n = len(candidate_daily_returns_pct)
    if n < block_days or block_days < 1 or samples < 1:
        raise ValueError("need at least one complete block and positive sample count")
    diffs = [float(a) - float(b) for a, b in zip(candidate_daily_returns_pct, benchmark_daily_returns_pct)]
    observed = sum(diffs) / n
    if observed <= 0:
        return 1.0
    centered = [x - observed for x in diffs]
    rng = random.Random(seed)
    blocks_per_sample = math.ceil(n / block_days)
    exceed = 0
    for _ in range(samples):
        draw = []
        for _block in range(blocks_per_sample):
            start = rng.randrange(n)
            draw.extend(centered[(start + k) % n] for k in range(block_days))
        null_mean = sum(draw[:n]) / n
        if null_mean >= observed:
            exceed += 1
    return (exceed + 1) / (samples + 1)


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, returned in original hypothesis order."""
    if not p_values:
        return []
    vals = [float(p) for p in p_values]
    if any(p < 0 or p > 1 for p in vals):
        raise ValueError("p-values must be in [0, 1]")
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    adjusted = [0.0] * len(vals)
    running = 0.0
    m = len(vals)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * vals[idx]))
        adjusted[idx] = running
    return adjusted


def evaluate_funding_gate(
    resolved_trades_by_asset: Mapping[str, int],
    strict_net_profit_pct: float,
    funding_vs_v4_p: float,
    funding_vs_buy_hold_p: float,
    daily_portfolio_returns_pct: Sequence[float],
    first_complete_run: bool = True,
) -> dict:
    """Evaluate the six locked gate clauses; does not launch or log a run."""
    trade_counts = {str(k): int(v) for k, v in resolved_trades_by_asset.items()}
    if any(v < 0 for v in trade_counts.values()):
        raise ValueError("resolved trade counts cannot be negative")
    total_trades = sum(trade_counts.values())
    active_assets = sum(v > 0 for v in trade_counts.values())
    adjusted = holm_adjust([funding_vs_v4_p, funding_vs_buy_hold_p])
    mdd = maximum_drawdown_pct(daily_portfolio_returns_pct)
    checks = {
        "1_min_300_trades_and_3_assets": total_trades >= 300 and active_assets >= 3,
        "2_strict_net_profit_positive": float(strict_net_profit_pct) > 0.0,
        "3_both_holm_adjusted_p_le_0_05": len(adjusted) == HOLM_HYPOTHESES and all(p <= ALPHA for p in adjusted),
        "4_daily_equity_max_drawdown_le_20pct": mdd <= 20.0,
        "5_first_complete_run_is_authoritative": bool(first_complete_run),
    }
    passed = all(checks.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "total_resolved_trades": total_trades,
        "assets_with_resolved_trades": active_assets,
        "holm_adjusted_p_values": adjusted,
        "max_drawdown_pct": mdd,
        "research_project_closed": not passed,
        "remaining_forward_test_only": not passed,
        "research_only": True,
        "live_orders": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSONL: ts,symbol,price,buy_volume,sell_volume,funding_rate")
    parser.add_argument("--funding", action="store_true")
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--train-window", type=int, default=300)
    args = parser.parse_args()
    bars, rates = [], []
    for line in Path(args.input).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        bars.append(MarketBar(ts=int(row["ts"]), symbol=str(row["symbol"]), price=float(row["price"]),
            buy_volume=float(row.get("buy_volume") or 0), sell_volume=float(row.get("sell_volume") or 0)))
        rates.append(None if row.get("funding_rate") is None else float(row["funding_rate"]))
    result = walk_forward_forecast(bars, horizon=args.horizon, train_window=args.train_window,
        funding_features=rates if args.funding else None, funding_enabled=args.funding)
    print(json.dumps({"available": result.get("available"), "resolved": result.get("resolved", 0),
        "feature_count": result.get("feature_count", 6), "funding_feature_enabled": args.funding,
        "research_only": True, "live_orders": False, "economic_gate_executed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
