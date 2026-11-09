"""Pinned v4 walk-forward reference copied from release commit 0630706.

Only shared dependencies are imported from the production module; the
walk_forward_forecast implementation below is the original release body.
"""
from mi_core.validated_forecast import _feature_cache, _labels_cache, _fit, _predict, _ret

def walk_forward_forecast(bars, horizon=5, train_window=300, min_train=60, flat_band=.0015, fit_every=1):
    if len(bars) < min_train + 25 + horizon:
        return {"available": False, "reason": "insufficient_history", "samples": len(bars)}

    feature_cache = _feature_cache(bars)
    label_cache = _labels_cache(bars, horizon, flat_band)
    preds = []
    correct = resolved = 0
    model = None
    next_fit_i = None
    fit_every = max(1, int(fit_every))

    for i in range(max(20, min_train), len(bars) - horizon):
        lo = max(20, i - train_window)
        X = []
        y = []
        # Labels require horizon future bars. At decision i, only outcomes
        # whose exit is at or before i are observable; exclude immature labels.
        for j in range(lo, i - horizon + 1):
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
        "model_version": "wf-logit-v4-price-flow-only",
        "research_only": True,
        "live_orders": False,
    }


