"""Independent research-only OHLC TP/SL evaluator."""
from math import isfinite


def _validate_bars(bars):
    previous_ts = None
    for i, bar in enumerate(bars):
        for key in ("ts", "open", "high", "low", "close"):
            if key not in bar:
                raise ValueError(f"bar {i} missing {key}")
            value = bar[key]
            if not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"bar {i} invalid {key}")
        o, h, lo, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
        if min(o, h, lo, c) <= 0 or lo > min(o, c) or h < max(o, c) or lo > h:
            raise ValueError(f"bar {i} has inconsistent OHLC")
        ts = bar["ts"]
        if previous_ts is not None and ts <= previous_ts:
            raise ValueError("bars must have strictly increasing timestamps")
        previous_ts = ts


def evaluate_signal(
    bars, signal_index, side, tp_pct, sl_pct, horizon,
    cost_pct=0.35, ambiguous_policy="unresolved",
):
    """Validate input, then evaluate one signal."""
    _validate_bars(bars)
    return _evaluate_signal_validated(
        bars, signal_index, side, tp_pct, sl_pct, horizon,
        cost_pct=cost_pct, ambiguous_policy=ambiguous_policy,
    )


def _evaluate_signal_validated(
    bars, signal_index, side, tp_pct, sl_pct, horizon,
    cost_pct=0.35, ambiguous_policy="unresolved",
):
    if side in ("LONG", "BUY", 1):
        d, name = 1, "LONG"
    elif side in ("SHORT", "SELL", -1):
        d, name = -1, "SHORT"
    else:
        raise ValueError("side must be LONG/SHORT, BUY/SELL, 1/-1")
    if not isinstance(signal_index, int) or signal_index < 0:
        raise ValueError("signal_index must be non-negative")
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be positive")
    if not all(isfinite(float(x)) for x in (tp_pct, sl_pct, cost_pct)):
        raise ValueError("TP, SL and cost must be finite")
    if tp_pct <= 0 or sl_pct <= 0 or cost_pct < 0:
        raise ValueError("TP/SL must be positive; cost cannot be negative")
    if ambiguous_policy not in ("unresolved", "stop_first"):
        raise ValueError("invalid ambiguous_policy")

    entry_i = signal_index + 1
    if entry_i >= len(bars):
        return {"status": "UNAVAILABLE_ENTRY", "side": name,
                "signal_index": signal_index, "entry_index": None,
                "exit_index": None, "net_pct": None}

    last_i = entry_i + horizon - 1
    if last_i >= len(bars):
        return {"status": "UNAVAILABLE_HORIZON", "side": name,
                "signal_index": signal_index, "entry_index": entry_i,
                "exit_index": None, "net_pct": None}

    entry = float(bars[entry_i]["open"])
    target = entry * (1 + d * tp_pct / 100)
    stop = entry * (1 - d * sl_pct / 100)

    def finish(status, i, price):
        gross = d * (price / entry - 1) * 100
        return {
            "status": status, "side": name, "signal_index": signal_index,
            "entry_index": entry_i, "exit_index": i,
            "entry_price": entry, "exit_price": price,
            "target_price": target, "stop_price": stop,
            "gross_pct": gross, "cost_pct": float(cost_pct),
            "net_pct": gross - float(cost_pct),
            "research_only": True, "live_orders": False,
        }

    for i in range(entry_i, last_i + 1):
        b = bars[i]
        o, h, lo = (float(b[k]) for k in ("open", "high", "low"))

        # The entry candle opens at entry, so only later opens can gap through levels.
        if i > entry_i:
            if (d == 1 and o <= stop) or (d == -1 and o >= stop):
                return finish("SL_GAP", i, o)
            if (d == 1 and o >= target) or (d == -1 and o <= target):
                return finish("TP_GAP", i, target)

        if d == 1:
            hit_tp, hit_sl = h >= target, lo <= stop
        else:
            hit_tp, hit_sl = lo <= target, h >= stop

        if hit_tp and hit_sl:
            if ambiguous_policy == "stop_first":
                return finish("SL_FIRST_ASSUMED", i, stop)
            return {
                "status": "AMBIGUOUS", "side": name,
                "signal_index": signal_index, "entry_index": entry_i,
                "exit_index": i, "entry_price": entry,
                "target_price": target, "stop_price": stop,
                "gross_pct": None, "cost_pct": float(cost_pct),
                "net_pct": None, "research_only": True, "live_orders": False,
            }
        if hit_tp:
            return finish("TP", i, target)
        if hit_sl:
            return finish("SL", i, stop)

    return finish("TIME_EXIT", last_i, float(bars[last_i]["close"]))


def summarize_trades(trades):
    resolved = [t for t in trades if isinstance(t.get("net_pct"), (int, float))]
    values = [float(t["net_pct"]) for t in resolved]
    wins = sum(x > 0 for x in values)
    profit = sum(x for x in values if x > 0)
    loss = -sum(x for x in values if x < 0)
    return {
        "trades_total": len(trades), "resolved": len(values),
        "ambiguous": sum(t.get("status") == "AMBIGUOUS" for t in trades),
        "wins": wins,
        "win_rate_pct": 100 * wins / len(values) if values else None,
        "avg_net_pct": sum(values) / len(values) if values else None,
        "sum_net_pct": sum(values) if values else None,
        "profit_factor": profit / loss if loss else (None if not profit else float("inf")),
        "research_only": True, "live_orders": False,
    }


def evaluate_signals(
    bars, signals, tp_pct, sl_pct, horizon, cost_pct=0.35,
    train_fraction=0.60, ambiguous_policy="unresolved",
):
    _validate_bars(bars)
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    split = int(len(bars) * train_fraction)
    train, test, accepted = [], [], []
    next_allowed = 0

    for s in sorted(signals, key=lambda x: x["signal_index"]):
        idx = s["signal_index"]
        if not isinstance(idx, int) or idx < next_allowed:
            continue
        trade = evaluate_signal(
            bars, idx, s["side"], tp_pct, sl_pct, horizon,
            cost_pct, ambiguous_policy,
        )
        if trade["status"].startswith("UNAVAILABLE"):
            continue
        exit_i = trade["exit_index"]
        if idx < split:
            if exit_i >= split:
                continue
            train.append(trade)
        else:
            test.append(trade)
        accepted.append(trade)
        next_allowed = exit_i + 1

    return {
        "model_version": "tpsl_path_eval_v1",
        "research_only": True, "live_orders": False,
        "bar_count": len(bars), "split_index": split,
        "tp_pct": float(tp_pct), "sl_pct": float(sl_pct),
        "horizon_bars": horizon, "round_trip_cost_pct": float(cost_pct),
        "train": summarize_trades(train), "test": summarize_trades(test),
        "trades": accepted,
        "warning": "Same-candle TP/SL order is unknown; AMBIGUOUS trades have no scored PnL. Research only.",
    }
