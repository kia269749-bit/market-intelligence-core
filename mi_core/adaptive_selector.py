"""Cost-aware rolling strategy tournament for research-only signal selection.

Historical outcomes use a next-bar entry and a fully resolved fixed horizon.
The selector is re-evaluated from new bars and never places orders.
"""
from __future__ import annotations

import math
import statistics
from typing import Sequence

from .models import MarketBar

STRATEGIES = ("momentum_5", "ema_trend", "breakout_20", "mean_reversion_14", "flow_5", "consensus_3")


def _ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = []
    value = float(values[0])
    for item in values:
        value = alpha * float(item) + (1.0 - alpha) * value
        out.append(value)
    return out


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    diffs = [float(closes[i]) - float(closes[i - 1]) for i in range(len(closes) - period, len(closes))]
    gains = sum(max(0.0, x) for x in diffs) / period
    losses = sum(max(0.0, -x) for x in diffs) / period
    if losses <= 1e-12:
        return 100.0 if gains > 1e-12 else 50.0
    rs = gains / losses
    return 100.0 - 100.0 / (1.0 + rs)


def _signal(bars: Sequence[MarketBar], i: int, strategy: str) -> int:
    if i < 30:
        return 0
    closes = [float(b.price) for b in bars[max(0, i - 60):i + 1]]
    if any(not math.isfinite(x) or x <= 0 for x in closes):
        return 0
    momentum = math.log(closes[-1] / closes[-6])
    recent_returns = [
        math.log(closes[k] / closes[k - 1])
        for k in range(max(1, len(closes) - 20), len(closes))
    ]
    volatility = statistics.pstdev(recent_returns) if len(recent_returns) > 1 else 0.0
    threshold = max(0.0008, volatility * math.sqrt(5.0) * 0.25)
    momentum_side = 1 if momentum > threshold else -1 if momentum < -threshold else 0

    ema8 = _ema(closes, 8)[-1]
    ema21 = _ema(closes, 21)[-1]
    trend_side = 1 if closes[-1] > ema8 > ema21 else -1 if closes[-1] < ema8 < ema21 else 0

    prior = bars[max(0, i - 20):i]
    prior_high = max(float(b.high if b.high is not None else b.price) for b in prior)
    prior_low = min(float(b.low if b.low is not None else b.price) for b in prior)
    current = float(bars[i].price)
    breakout_side = 1 if current > prior_high * 1.0002 else -1 if current < prior_low * 0.9998 else 0

    rsi = _rsi(closes, 14)
    mean_reversion_side = 1 if rsi <= 30.0 else -1 if rsi >= 70.0 else 0

    flow_values = []
    for bar in bars[max(0, i - 4):i + 1]:
        buy = max(0.0, float(bar.buy_volume or 0.0))
        sell = max(0.0, float(bar.sell_volume or 0.0))
        total = buy + sell
        if total > 0:
            flow_values.append((buy - sell) / total)
    flow = statistics.fmean(flow_values) if flow_values else 0.0
    flow_side = 1 if flow >= 0.15 else -1 if flow <= -0.15 else 0

    if strategy == "momentum_5":
        return momentum_side
    if strategy == "ema_trend":
        return trend_side
    if strategy == "breakout_20":
        return breakout_side
    if strategy == "mean_reversion_14":
        return mean_reversion_side
    if strategy == "flow_5":
        return flow_side
    if strategy == "consensus_3":
        score = momentum_side + trend_side + breakout_side
        return 1 if score >= 2 else -1 if score <= -2 else 0
    return 0


def _net_return(bars, signal_index, direction, horizon, cost_pct):
    """Realized net percent return, entering next bar and exiting after horizon bars."""
    entry_index = signal_index + 1
    exit_index = signal_index + horizon + 1
    if entry_index >= len(bars) or exit_index >= len(bars):
        return None
    entry_bar = bars[entry_index]
    entry = float(entry_bar.open if entry_bar.open is not None and entry_bar.open > 0 else entry_bar.price)
    exit_price = float(bars[exit_index].price)
    if entry <= 0 or exit_price <= 0 or not math.isfinite(entry) or not math.isfinite(exit_price):
        return None
    gross = int(direction) * (exit_price / entry - 1.0) * 100.0
    return gross - float(cost_pct)


def _metrics(returns):
    values = [float(x) for x in returns if x is not None and math.isfinite(float(x))]
    n = len(values)
    if not n:
        return {"trades": 0, "win_rate": 0.0, "mean_net_pct": 0.0,
                "net_profit_pct": 0.0, "profit_factor": 0.0,
                "ci_lower_pct": 0.0, "recent_mean_net_pct": 0.0,
                "max_drawdown_pct": 0.0}
    wins = sum(x for x in values if x > 0)
    losses = -sum(x for x in values if x < 0)
    mean = statistics.fmean(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    equity = peak = max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": n,
        "win_rate": round(sum(x > 0 for x in values) / n, 4),
        "mean_net_pct": round(mean, 6),
        "net_profit_pct": round(sum(values), 6),
        "profit_factor": round(wins / losses, 4) if losses > 0 else (99.0 if wins > 0 else 0.0),
        "ci_lower_pct": round(mean - 1.96 * std / math.sqrt(n), 6),
        "recent_mean_net_pct": round(statistics.fmean(values[-20:]), 6),
        "max_drawdown_pct": round(max_dd, 6),
    }


def _training_gate(metrics, min_trades):
    return (
        metrics["trades"] >= min_trades
        and metrics["mean_net_pct"] > 0
        and metrics["profit_factor"] >= 1.15
        and metrics["ci_lower_pct"] > 0
        and metrics["recent_mean_net_pct"] > 0
    )


def evaluate_adaptive_selection(
    bars: Sequence[MarketBar],
    horizon: int = 60,
    cost_pct: float = 0.35,
    train_window: int = 300,
    min_train_trades: int = 20,
    min_oos_trades: int = 12,
):
    """Rank strategy families and validate the selection process walk-forward.

    The current candidate is not considered proven merely because it wins in
    its training window. Acceptance requires a separate rolling selector test
    on later, previously unseen outcomes after costs.
    """
    if horizon < 1 or cost_pct < 0 or train_window < 60:
        raise ValueError("invalid horizon, cost, or train_window")
    n = len(bars)
    if n < max(80, horizon + 40):
        return {
            "available": False, "reason": "insufficient_history", "samples": n,
            "accepted": False, "research_only": True, "live_orders": False,
        }

    signals = {name: [_signal(bars, i, name) for i in range(n)] for name in STRATEGIES}
    outcomes = {name: [None] * n for name in STRATEGIES}
    for name in STRATEGIES:
        for i, direction in enumerate(signals[name]):
            if direction:
                outcomes[name][i] = _net_return(bars, i, direction, horizon, cost_pct)

    def resolved_returns(name, decision_index, start_index):
        # Include only trades whose full outcome was known by decision_index.
        stop = max(0, decision_index - horizon)
        lo = max(0, start_index)
        return [
            outcomes[name][j]
            for j in range(lo, min(stop, n))
            if signals[name][j] and outcomes[name][j] is not None
        ]

    current_i = n - 1
    candidates = []
    for name in STRATEGIES:
        train = _metrics(resolved_returns(name, current_i, n - train_window - horizon - 1))
        candidates.append({
            "strategy": name,
            "current_direction": signals[name][current_i],
            "training": train,
            "training_gate": _training_gate(train, min_train_trades),
        })

    # Nested walk-forward simulation: each historical decision sees only
    # trades whose exit happened before that decision.
    oos_returns = []
    oos_choices = []
    oos_start = max(60, n - max(180, train_window // 2))
    for i in range(oos_start, n - horizon - 1):
        ranked = []
        for name in STRATEGIES:
            train = _metrics(resolved_returns(name, i, i - train_window - horizon - 1))
            if _training_gate(train, min_train_trades) and signals[name][i]:
                ranked.append((train["ci_lower_pct"], train["mean_net_pct"], name))
        if not ranked:
            continue
        _, _, chosen = max(ranked)
        outcome = outcomes[chosen][i]
        if outcome is not None:
            oos_returns.append(outcome)
            oos_choices.append(chosen)

    oos = _metrics(oos_returns)
    oos_accepted = (
        oos["trades"] >= min_oos_trades
        and oos["mean_net_pct"] > 0
        and oos["profit_factor"] >= 1.15
        and oos["ci_lower_pct"] > 0
        and oos["recent_mean_net_pct"] > 0
    )
    eligible = [x for x in candidates if x["training_gate"] and x["current_direction"]]
    if eligible:
        chosen = max(eligible, key=lambda x: (
            x["training"]["ci_lower_pct"], x["training"]["mean_net_pct"],
            x["training"]["profit_factor"], x["training"]["trades"]
        ))
    else:
        active = [x for x in candidates if x["current_direction"]]
        chosen = max(active or candidates, key=lambda x: (
            x["training"]["ci_lower_pct"], x["training"]["mean_net_pct"],
            x["training"]["profit_factor"], x["training"]["trades"]
        ))

    accepted = bool(oos_accepted and chosen["training_gate"] and chosen["current_direction"])
    reasons = []
    if not chosen["current_direction"]:
        reasons.append("no_active_strategy_signal")
    if not chosen["training_gate"]:
        reasons.append("training_edge_not_proven")
    if oos["trades"] < min_oos_trades:
        reasons.append("insufficient_walk_forward_oos_trades")
    elif not oos_accepted:
        reasons.append("walk_forward_oos_edge_not_proven")

    return {
        "available": True,
        "asset": bars[-1].symbol,
        "horizon_bars": horizon,
        "cost_pct": float(cost_pct),
        "samples": n,
        "selected_strategy": chosen["strategy"],
        "direction": "BULLISH" if chosen["current_direction"] > 0 else "BEARISH" if chosen["current_direction"] < 0 else "NONE",
        "current_signal": int(chosen["current_direction"]),
        "training": chosen["training"],
        "training_gate": bool(chosen["training_gate"]),
        "walk_forward_oos": oos,
        "oos_strategy_counts": {name: oos_choices.count(name) for name in STRATEGIES},
        "accepted": accepted,
        "status": "EDGE_VALIDATED" if accepted else "EDGE_UNPROVEN",
        "reasons": reasons,
        "candidates": candidates,
        "selection_method": "rolling net-expectancy + lower-confidence-bound; nested walk-forward selection",
        "research_only": True,
        "live_orders": False,
    }
