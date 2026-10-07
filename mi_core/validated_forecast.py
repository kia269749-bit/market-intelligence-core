"""Validated, lightweight probabilistic forecaster. Research-only, no orders."""
from __future__ import annotations
import math, statistics
from .models import MarketBar


def _ret(a, b):
    return math.log(a / b) if a > 0 and b > 0 else 0.0


def _feat(bars, i):
    if i < 20:
        return None
    rs = [_ret(bars[k].price, bars[k - 1].price) for k in range(1, i + 1)]
    vol = statistics.pstdev(rs[-20:]) or 1e-8
    flow = []
    for b in bars[:i + 1]:
        buy = float(b.buy_volume or 0)
        sell = float(b.sell_volume or 0)
        den = buy + sell
        flow.append((buy - sell) / den if den else 0)
    oi = 0
    if bars[i].oi is not None and bars[i - 1].oi not in (None, 0):
        oi = float(bars[i].oi) / float(bars[i - 1].oi) - 1
    return [
        sum(rs[-5:]) / vol,
        sum(rs[-10:]) / (vol * 2 ** .5),
        sum(rs[-20:]) / (vol * 4),
        sum(flow[-5:]) / 5,
        sum(flow[-20:]) / 20,
        oi * 100,
        float(bars[i].funding or 0) * 10000,
        vol,
    ]


def _label(bars, i, h, band):
    if i + h >= len(bars):
        return None
    r = _ret(bars[i + h].price, bars[i].price)
    return 1 if r > band else -1 if r < -band else 0


def _feature_cache(bars):
    """Build per-index features once. The old path recomputed O(i) history for every i."""
    n = len(bars)
    out = [None] * n
    if n < 21:
        return out

    returns = [0.0] * n
    flow = [0.0] * n
    for i in range(1, n):
        returns[i] = _ret(bars[i].price, bars[i - 1].price)
    for i, b in enumerate(bars):
        buy = float(b.buy_volume or 0)
        sell = float(b.sell_volume or 0)
        den = buy + sell
        flow[i] = (buy - sell) / den if den else 0.0

    prefix_r = [0.0] * (n + 1)
    prefix_f = [0.0] * (n + 1)
    prefix_r2 = [0.0] * (n + 1)
    for i in range(n):
        prefix_r[i + 1] = prefix_r[i] + returns[i]
        prefix_f[i + 1] = prefix_f[i] + flow[i]
        prefix_r2[i + 1] = prefix_r2[i] + returns[i] * returns[i]

    for i in range(20, n):
        start20 = i - 19
        count20 = 20
        sum20 = prefix_r[i + 1] - prefix_r[start20]
        sum20_2 = prefix_r2[i + 1] - prefix_r2[start20]
        mean20 = sum20 / count20
        variance20 = max(0.0, sum20_2 / count20 - mean20 * mean20)
        vol = math.sqrt(variance20) or 1e-8

        def rsum(window):
            start = max(0, i - window + 1)
            return prefix_r[i + 1] - prefix_r[start]

        def fsum(window):
            start = max(0, i - window + 1)
            return prefix_f[i + 1] - prefix_f[start]

        oi = 0.0
        if bars[i].oi is not None and bars[i - 1].oi not in (None, 0):
            oi = float(bars[i].oi) / float(bars[i - 1].oi) - 1

        out[i] = [
            rsum(5) / vol,
            rsum(10) / (vol * 2 ** .5),
            rsum(20) / (vol * 4),
            fsum(5) / 5,
            fsum(20) / 20,
            oi * 100,
            float(bars[i].funding or 0) * 10000,
            vol,
        ]
    return out


def _labels_cache(bars, horizon, flat_band):
    """Precompute labels once per horizon."""
    n = len(bars)
    labels = [None] * n
    for i in range(max(0, n - horizon)):
        labels[i] = _label(bars, i, horizon, flat_band)
    return labels


def _fit(X, y, epochs=50, lr=.035, l2=.02):
    means = [sum(x[j] for x in X) / len(X) for j in range(len(X[0]))]
    scales = [statistics.pstdev(x[j] for x in X) or 1 for j in range(len(X[0]))]
    Z = [[(x[j] - means[j]) / scales[j] for j in range(len(x))] for x in X]
    W = [[0.0] * len(X[0]) for _ in range(3)]
    B = [0.0] * 3
    cls = (-1, 0, 1)
    for _ in range(epochs):
        for z, t in zip(Z, y):
            q = [sum(W[k][j] * z[j] for j in range(len(z))) + B[k] for k in range(3)]
            m = max(q)
            e = [math.exp(max(-20, min(20, v - m))) for v in q]
            s = sum(e)
            p = [v / s for v in e]
            ti = cls.index(t)
            for k in range(3):
                er = p[k] - (k == ti)
                for j in range(len(z)):
                    W[k][j] -= lr * (er * z[j] + l2 * W[k][j])
                B[k] -= lr * er
    return means, scales, W, B, cls


def _predict(m, x):
    means, scales, W, B, cls = m
    z = [(x[j] - means[j]) / scales[j] for j in range(len(x))]
    q = [sum(W[k][j] * z[j] for j in range(len(z))) + B[k] for k in range(3)]
    mx = max(q)
    e = [math.exp(max(-20, min(20, v - mx))) for v in q]
    s = sum(e)
    p = [v / s for v in e]
    return {cls[k]: p[k] for k in range(3)}


def walk_forward_forecast(bars, horizon=5, train_window=300, min_train=60, flat_band=.0015, fit_every=1, purge_bars=0):
    if len(bars) < min_train + 25 + horizon:
        return {"available": False, "reason": "insufficient_history", "samples": len(bars)}

    feature_cache = _feature_cache(bars)
    label_cache = _labels_cache(bars, horizon, flat_band)
    preds = []
    correct = resolved = 0
    model = None
    next_fit_i = None
    fit_every = max(1, int(fit_every))
    purge_bars = max(0, int(purge_bars))

    for i in range(max(20, min_train), len(bars) - horizon):
        lo = max(20, i - train_window)
        train_end = max(lo, i - purge_bars)
        X = []
        y = []
        for j in range(lo, train_end):
            f = feature_cache[j]
            lab = label_cache[j]
            if f is not None and lab is not None:
                X.append(f)
                y.append(lab)
        if len(X) < min_train:
            continue

        if model is None or next_fit_i is None or i >= next_fit_i:
            model = _fit(X, y)
            next_fit_i = i + fit_every

        x = feature_cache[i]
        if x is None:
            continue
        p = _predict(model, x)
        pred = max(p, key=p.get)
        actual = label_cache[i]

        future_returns = [
            _ret(bars[k].price, bars[i].price) * 100.0
            for k in range(i + 1, min(i + horizon + 1, len(bars)))
        ]
        future_max = max(future_returns) if future_returns else 0.0
        future_min = min(future_returns) if future_returns else 0.0
        favorable_mfe = future_max if pred == 1 else -future_min
        adverse_mae = -future_min if pred == 1 else future_max
        preds.append({
            "ts": bars[i].ts,
            "pred": pred,
            "actual": actual,
            "actual_return_pct": round(_ret(bars[i + horizon].price, bars[i].price) * 100, 6)
            if i + horizon < len(bars) else None,
            "future_max_return_pct": round(future_max, 6),
            "future_min_return_pct": round(future_min, 6),
            "favorable_mfe_pct": round(favorable_mfe, 6),
            "adverse_mae_pct": round(adverse_mae, 6),
            "p_up": p[1],
            "p_flat": p[0],
            "p_down": p[-1],
        })
        if actual is not None:
            resolved += 1
            correct += int(pred == actual)

    return {
        "available": bool(preds),
        "horizon_bars": horizon,
        "resolved": resolved,
        "accuracy": round(correct / resolved, 6) if resolved else 0,
        "predictions": preds,
        "model_version": "wf-logit-v2",
        "purge_bars": purge_bars,
        "research_only": True,
        "live_orders": False,
    }


def forecast_now(bars, horizon=5, train_window=300, flat_band=.0015):
    if len(bars) < 100:
        return {"available": False, "reason": "insufficient_history", "samples": len(bars)}
    i = len(bars) - 1
    feature_cache = _feature_cache(bars)
    label_cache = _labels_cache(bars, horizon, flat_band)
    X = []
    y = []
    for j in range(max(20, i - train_window), i):
        f = feature_cache[j]
        lab = label_cache[j]
        if f is not None and lab is not None:
            X.append(f)
            y.append(lab)
    if len(X) < 60 or feature_cache[i] is None:
        return {"available": False, "reason": "insufficient_training_samples", "samples": len(X)}
    p = _predict(_fit(X, y), feature_cache[i])
    direction = {1: "UP", 0: "FLAT", -1: "DOWN"}[max(p, key=p.get)]
    rs = [_ret(bars[k].price, bars[k - 1].price) for k in range(max(1, i - 19), i + 1)]
    vol = statistics.pstdev(rs) or 1e-8
    exp = (p[1] - p[-1]) * vol * math.sqrt(horizon) * 100
    band = 1.96 * vol * math.sqrt(horizon) * 100
    short = sum(rs[-5:])
    reversal = (short < 0 and direction == "UP") or (short > 0 and direction == "DOWN")
    breakout = min(.95, max(.05, .5 + abs(short) / (vol * 5) * .12))
    current_move_pct = short * 100.0
    return {
        "available": True,
        "ts": bars[i].ts,
        "symbol": bars[i].symbol,
        "horizon_bars": horizon,
        "direction": direction,
        "p_up": round(p[1], 4),
        "p_flat": round(p[0], 4),
        "p_down": round(p[-1], 4),
        "expected_return_pct": round(exp, 4),
        "lower_return_pct": round(exp - band, 4),
        "upper_return_pct": round(exp + band, 4),
        "confidence": round(max(p.values()), 4),
        "reversal_warning": reversal,
        "breakout_probability": round(breakout, 4),
        "current_move_pct": round(current_move_pct, 4),
        "model_version": "wf-logit-v2",
        "research_only": True,
        "live_orders": False,
    }


def score_predictions(result):
    """Compute OOS accuracy, per-class precision/recall and confidence calibration."""
    rows = [x for x in result.get("predictions", []) if x.get("actual") is not None]
    if not rows:
        return {"resolved": 0, "accuracy": 0.0, "precision": {}, "recall": {}, "high_conf_accuracy": 0.0}
    metrics = {}
    for c in (-1, 0, 1):
        tp = sum(x["pred"] == c and x["actual"] == c for x in rows)
        fp = sum(x["pred"] == c and x["actual"] != c for x in rows)
        fn = sum(x["pred"] != c and x["actual"] == c for x in rows)
        metrics[str(c)] = {
            "precision": round(tp / (tp + fp), 6) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 6) if tp + fn else 0.0,
        }
    correct = sum(x["pred"] == x["actual"] for x in rows)
    high = [x for x in rows if max(x["p_up"], x["p_flat"], x["p_down"]) >= .70]
    high_correct = sum(x["pred"] == x["actual"] for x in high)
    return {
        "resolved": len(rows),
        "accuracy": round(correct / len(rows), 6),
        "precision": {k: v["precision"] for k, v in metrics.items()},
        "recall": {k: v["recall"] for k, v in metrics.items()},
        "high_conf_samples": len(high),
        "high_conf_accuracy": round(high_correct / len(high), 6) if high else 0.0,
    }


def forecast_acceptance_gate(metrics, capital_metrics, min_oos_samples=100, min_high_conf_samples=20, min_high_conf_accuracy=0.55, min_profit_hit_rate=0.30, preferred_profit_hit_rate=0.15):
    """Conservative research gate. No orders are created."""
    reasons = []
    resolved = int(metrics.get("resolved", 0))
    high_n = int(metrics.get("high_conf_samples", 0))
    high_acc = float(metrics.get("high_conf_accuracy", 0.0))
    min_hit = float(capital_metrics.get("min_target_hit_rate", 0.0))
    pref_hit = float(capital_metrics.get("preferred_target_hit_rate", 0.0))
    if resolved < min_oos_samples:
        reasons.append("insufficient_oos_samples")
    if high_n < min_high_conf_samples:
        reasons.append("insufficient_high_conf_samples")
    if high_n >= min_high_conf_samples and high_acc < min_high_conf_accuracy:
        reasons.append("weak_high_conf_accuracy")
    if min_hit < min_profit_hit_rate:
        reasons.append("weak_usd4_target_hit_rate")
    if pref_hit < preferred_profit_hit_rate:
        reasons.append("weak_usd10_target_hit_rate")
    return {
        "accepted": not reasons,
        "status": "PASS" if not reasons else "NO_TRADE",
        "reasons": reasons,
        "thresholds": {
            "min_oos_samples": min_oos_samples,
            "min_high_conf_samples": min_high_conf_samples,
            "min_high_conf_accuracy": min_high_conf_accuracy,
            "min_usd4_hit_rate": min_profit_hit_rate,
            "min_usd10_hit_rate": preferred_profit_hit_rate,
        },
        "research_only": True,
        "live_orders": False,
    }


def score_capital_targets(result, capital_usd=500.0, min_profit_usd=4.0, preferred_profit_usd=10.0, round_trip_cost_pct=0.35):
    """Score OOS directional predictions against $4 minimum / $10 preferred net targets."""
    rows = [
        x for x in result.get("predictions", [])
        if x.get("actual_return_pct") is not None and x.get("pred") in (-1, 1)
    ]
    min_move = min_profit_usd / capital_usd * 100.0 + round_trip_cost_pct
    preferred_move = preferred_profit_usd / capital_usd * 100.0 + round_trip_cost_pct
    min_hits = preferred_hits = directional = 0
    for x in rows:
        directional += 1
        r = float(x["actual_return_pct"])
        favorable = r if x["pred"] == 1 else -r
        min_hits += favorable >= min_move
        preferred_hits += favorable >= preferred_move
    return {
        "resolved_directional": directional,
        "min_profit_usd": min_profit_usd,
        "preferred_profit_usd": preferred_profit_usd,
        "min_required_move_pct": round(min_move, 4),
        "preferred_required_move_pct": round(preferred_move, 4),
        "min_target_hit_rate": round(min_hits / directional, 6) if directional else 0.0,
        "preferred_target_hit_rate": round(preferred_hits / directional, 6) if directional else 0.0,
        "research_only": True,
        "live_orders": False,
    }
