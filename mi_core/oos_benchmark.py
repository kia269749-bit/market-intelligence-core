"""Compare directional OOS predictions with buy-and-hold and random baselines.

Metrics are per non-overlapping forecast trade, not annualized Sharpe. Research-only.
"""
from __future__ import annotations
import math, random
from statistics import mean, pstdev

def _stats(returns_pct, capital_usd):
    equity = float(capital_usd); peak = equity; max_dd = 0.0; pnls = []
    for pct in returns_pct:
        pnl = capital_usd * pct / 100.0; pnls.append(pnl); equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
    avg = mean(returns_pct) if returns_pct else 0.0
    vol = pstdev(returns_pct) if len(returns_pct) > 1 else 0.0
    return {"trades": len(returns_pct), "net_profit_usd": round(sum(pnls), 4),
            "ending_equity_usd": round(equity, 4), "max_drawdown_pct": round(max_dd*100, 6),
            "sharpe_per_trade_not_annualized": round(avg/vol, 6) if vol else None,
            "win_rate": round(sum(x > 0 for x in returns_pct)/len(returns_pct), 6) if returns_pct else 0.0,
            "mean_net_return_pct": round(avg, 6)}

def compare_oos_baselines(result, *, cost_policy="strict", capital_usd=500.0, horizon_bars=None, seed=20261030):
    """Compare model, long-only buy/hold and seeded random directions.

    Uses only chronologically non-overlapping forecast outcomes. Costs are
    charged once per completed round trip. The Sharpe value is per-trade.
    """
    from .costs import get_round_trip_cost_pct
    cost = get_round_trip_cost_pct(cost_policy)
    if isinstance(capital_usd, bool): raise ValueError("capital_usd must be finite and positive")
    try: capital = float(capital_usd)
    except (TypeError, ValueError, OverflowError): raise ValueError("capital_usd must be finite and positive") from None
    if not math.isfinite(capital) or capital <= 0: raise ValueError("capital_usd must be finite and positive")
    rows = []
    for row in result.get("predictions", []):
        if row.get("pred") not in (-1, 1) or row.get("actual_return_pct") is None: continue
        try: ts, pred, actual = int(row["ts"]), int(row["pred"]), float(row["actual_return_pct"])
        except (KeyError, TypeError, ValueError, OverflowError): continue
        if math.isfinite(actual): rows.append((ts, pred, actual))
    rows.sort(key=lambda x: x[0])
    if horizon_bars is None: horizon_bars = int(result.get("horizon_bars", 1))
    if isinstance(horizon_bars, bool) or int(horizon_bars) < 1: raise ValueError("horizon_bars must be positive")
    inferred_deltas = [b[0] - a[0] for a, b in zip(rows, rows[1:]) if b[0] > a[0]]
    inferred_interval = sorted(inferred_deltas)[len(inferred_deltas)//2] if inferred_deltas else 60_000
    interval_ms = int(result.get("bar_interval_ms", inferred_interval))
    if interval_ms <= 0: raise ValueError("bar_interval_ms must be positive")
    selected, next_allowed = [], None
    for row in rows:
        if next_allowed is None or row[0] >= next_allowed:
            selected.append(row); next_allowed = row[0] + int(horizon_bars)*interval_ms
    rng = random.Random(seed); model=[]; hold=[]; random_returns=[]
    for _, pred, actual in selected:
        model.append((actual if pred == 1 else -actual) - cost)
        hold.append(actual - cost)
        side = 1 if rng.random() >= 0.5 else -1
        random_returns.append((actual if side == 1 else -actual) - cost)
    return {"available": bool(selected), "cost_policy": cost_policy, "round_trip_cost_pct": cost,
            "capital_usd": capital, "horizon_bars": int(horizon_bars), "bar_interval_ms": interval_ms,
            "non_overlapping_oos_samples": len(selected), "random_seed": seed,
            "model": _stats(model, capital), "buy_and_hold": _stats(hold, capital),
            "random_direction": _stats(random_returns, capital), "research_only": True, "live_orders": False,
            "sharpe_note": "per-trade, not annualized; not comparable across different horizons as annualized Sharpe"}