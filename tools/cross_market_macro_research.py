"""Research whether lagged external-market returns add BTC OOS trading value.

Downloads public FRED CSV series without credentials. All macro features are lagged
by at least two calendar days relative to the BTC daily candle date to reduce
close-time leakage. Research only; never places orders.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import time
from urllib.error import URLError
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mi_core.storage import load_bars

FRED_SERIES = {
    "usd_broad": "DTWEXBGS",
    "sp500": "SP500",
    "gold": "GOLDAMGBD228NLBM",
    "wti_oil": "DCOILWTICO",
    "vix": "VIXCLS",
}


def parse_fred_csv(text, series_id):
    rows = csv.DictReader(io.StringIO(text))
    result = []
    for row in rows:
        date_text = row.get("observation_date") or row.get("DATE") or row.get("observation_date".upper())
        value_text = row.get(series_id)
        if not date_text or not value_text or value_text.strip() in {"", "."}:
            continue
        try:
            d = date.fromisoformat(date_text.strip())
            value = float(value_text)
        except (ValueError, TypeError):
            continue
        if math.isfinite(value) and value > 0:
            result.append((d, value))
    result.sort(key=lambda x: x[0])
    dedup = {d: value for d, value in result}
    return sorted(dedup.items())


def fetch_fred_series(series_id, timeout=30, attempts=3):
    """Fetch public FRED data with bounded retries for transient runner/network timeouts."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + series_id
    req = Request(url, headers={"User-Agent": "market-intelligence-core/1.0"})
    last_error = None
    for attempt in range(attempts):
        try:
            with urlopen(req, timeout=timeout) as response:
                payload = response.read().decode("utf-8-sig")
            result = parse_fred_csv(payload, series_id)
            if len(result) < 100:
                raise RuntimeError(f"FRED series {series_id} returned only {len(result)} valid observations")
            return result
        except (TimeoutError, OSError, URLError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch FRED series {series_id} after {attempts} attempts: {last_error}")


def _lagged_change(series, cutoff):
    eligible = [item for item in series if item[0] <= cutoff]
    if len(eligible) < 2:
        return None
    prior_date, prior_value = eligible[-2]
    current_date, current_value = eligible[-1]
    if prior_value <= 0:
        return None
    # Require a recent observation, but allow weekends and market holidays.
    if (cutoff - current_date).days > 7:
        return None
    return current_value / prior_value - 1.0


def build_aligned_dataset(bars, macro_series):
    rows = sorted(bars, key=lambda b: int(b.ts))
    result = []
    for i in range(1, len(rows)):
        prev_open = getattr(rows[i - 1], "open", None)
        current_open = getattr(rows[i], "open", None)
        try:
            prev_open, current_open = float(prev_open), float(current_open)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(prev_open) and math.isfinite(current_open) and prev_open > 0 and current_open > 0):
            continue
        target_date = datetime.fromtimestamp(int(rows[i].ts) / 1000, tz=timezone.utc).date()
        cutoff = target_date - timedelta(days=2)
        features = {}
        for feature_name, series in macro_series.items():
            change = _lagged_change(series, cutoff)
            if change is None:
                break
            features[feature_name] = change * 100.0
        if len(features) != len(macro_series):
            continue
        result.append({
            "date": target_date.isoformat(),
            "ts": int(rows[i].ts),
            "features": features,
            "target_return_pct": (current_open / prev_open - 1.0) * 100.0,
        })
    return result


def _solve(matrix, vector):
    """Small pure-Python Gaussian elimination with partial pivoting."""
    a = [list(map(float, row)) + [float(vector[i])] for i, row in enumerate(matrix)]
    n = len(a)
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("Singular regression design matrix")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [x / scale for x in a[col]]
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor:
                a[row] = [a[row][j] - factor * a[col][j] for j in range(n + 1)]
    return [a[i][-1] for i in range(n)]


def fit_ols(train_rows, feature_names):
    if len(train_rows) < max(100, len(feature_names) * 20):
        raise ValueError("Not enough training rows for macro OLS")
    means, scales = {}, {}
    for name in feature_names:
        vals = [row["features"][name] for row in train_rows]
        mu = sum(vals) / len(vals)
        variance = sum((v - mu) ** 2 for v in vals) / len(vals)
        sd = math.sqrt(variance)
        means[name] = mu
        scales[name] = sd if sd > 1e-9 else 1.0
    design = []
    targets = []
    for row in train_rows:
        design.append([1.0] + [(row["features"][name] - means[name]) / scales[name] for name in feature_names])
        targets.append(row["target_return_pct"])
    xtx = [[sum(x[i] * x[j] for x in design) for j in range(len(feature_names) + 1)] for i in range(len(feature_names) + 1)]
    xty = [sum(x[i] * y for x, y in zip(design, targets)) for i in range(len(feature_names) + 1)]
    # Small ridge penalty on slopes only to stabilize correlated macro series.
    for i in range(1, len(xtx)):
        xtx[i][i] += 1e-6
    coef = _solve(xtx, xty)
    return {"means": means, "scales": scales, "coefficients": coef, "features": list(feature_names)}


def predict(model, row):
    values = [1.0]
    for name in model["features"]:
        values.append((row["features"][name] - model["means"][name]) / model["scales"][name])
    return sum(a * b for a, b in zip(model["coefficients"], values))


def _metrics(rows, predictions, *, cost_pct, capital_usd, threshold_pct):
    equity = float(capital_usd)
    peak = equity
    max_dd = 0.0
    prev_pos = 0.0
    returns = []
    positions = []
    costs = []
    for row, prediction in zip(rows, predictions):
        position = 1.0 if prediction > threshold_pct else (-1.0 if prediction < -threshold_pct else 0.0)
        cost = abs(position - prev_pos) * cost_pct / 2.0
        net_pct = position * row["target_return_pct"] - cost
        equity *= max(0.0, 1.0 + net_pct / 100.0)
        peak = max(peak, equity)
        if peak:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        returns.append(net_pct)
        positions.append(position)
        costs.append(cost)
        prev_pos = position
    n = len(rows)
    directional = [1.0 if (p > 0 and r["target_return_pct"] > 0) or (p < 0 and r["target_return_pct"] < 0) else 0.0
                   for r, p in zip(rows, predictions) if p != 0]
    active = sum(1 for p in positions if p != 0)
    net_profit = equity - capital_usd
    return {
        "samples": n,
        "traded_bars": active,
        "position_changes": sum(1 for i, p in enumerate(positions) if p != (positions[i - 1] if i else 0.0)),
        "directional_accuracy_when_forecast_nonzero": round(sum(directional) / len(directional), 4) if directional else None,
        "net_profit_usd": round(net_profit, 4),
        "net_return_pct": round(net_profit / capital_usd * 100.0, 4) if capital_usd else 0.0,
        "estimated_cost_sum_pct": round(sum(costs), 4),
        "max_drawdown_pct": round(max_dd, 4),
        "exposure_pct": round(active / n * 100.0, 2) if n else 0.0,
        "ending_equity_usd": round(equity, 4),
        "threshold_pct": threshold_pct,
    }


def run_research(bars, macro_series, *, cost_round_trip_pct=0.35, capital_usd=500.0):
    dataset = build_aligned_dataset(bars, macro_series)
    if len(dataset) < 300:
        return {
            "status": "insufficient_aligned_data",
            "aligned_samples": len(dataset),
            "research_only": True,
            "live_orders": False,
            "trade_ready": False,
        }
    split = int(len(dataset) * 0.70)
    train, holdout = dataset[:split], dataset[split:]
    feature_names = list(macro_series)
    model = fit_ols(train, feature_names)
    predictions = [predict(model, row) for row in holdout]
    actual = [row["target_return_pct"] for row in holdout]
    directional = sum(1 for p, y in zip(predictions, actual) if (p > 0 and y > 0) or (p < 0 and y < 0))
    nonzero = sum(1 for p in predictions if p != 0)
    buy_hold = _metrics(holdout, [1e9] * len(holdout), cost_pct=0.0, capital_usd=capital_usd, threshold_pct=0.0)
    # Cost-aware threshold: only trade if the frozen model's predicted absolute
    # daily return is at least the assumed full round-trip cost.
    cost_aware = _metrics(holdout, predictions, cost_pct=cost_round_trip_pct,
                          capital_usd=capital_usd, threshold_pct=cost_round_trip_pct)
    directional_only = _metrics(holdout, predictions, cost_pct=cost_round_trip_pct,
                                 capital_usd=capital_usd, threshold_pct=0.0)
    return {
        "status": "ok",
        "symbol": bars[-1].symbol if bars else None,
        "macro_series": FRED_SERIES,
        "aligned_samples": len(dataset),
        "training_samples": len(train),
        "holdout_samples": len(holdout),
        "train_start": train[0]["date"],
        "train_end": train[-1]["date"],
        "holdout_start": holdout[0]["date"],
        "holdout_end": holdout[-1]["date"],
        "macro_lag_policy": "For a target BTC candle date D, each macro return uses observations no later than D-2 calendar days.",
        "forecast_directional_accuracy": round(directional / nonzero, 4) if nonzero else None,
        "mean_absolute_forecast_pct": round(sum(abs(p) for p in predictions) / len(predictions), 6),
        "cost_round_trip_pct": cost_round_trip_pct,
        "buy_and_hold_baseline": buy_hold,
        "macro_ols_direction_only": directional_only,
        "macro_ols_cost_aware": cost_aware,
        "model": model,
        "research_only": True,
        "live_orders": False,
        "trade_ready": False,
        "trade_readiness_reason": "External macro features are exploratory; require multiple untouched windows, a forecast-vs-baseline lift, cost robustness, and paper-shadow validation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cost-round-trip-pct", type=float, default=0.35)
    parser.add_argument("--capital", type=float, default=500.0)
    args = parser.parse_args()
    bars = load_bars(args.crypto_input)
    macro = {name: fetch_fred_series(series_id) for name, series_id in FRED_SERIES.items()}
    result = run_research(bars, macro, cost_round_trip_pct=args.cost_round_trip_pct, capital_usd=args.capital)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": result.get("status"),
        "symbol": result.get("symbol"),
        "aligned_samples": result.get("aligned_samples"),
        "forecast_directional_accuracy": result.get("forecast_directional_accuracy"),
        "buy_and_hold_oos_return_pct": (result.get("buy_and_hold_baseline") or {}).get("net_return_pct"),
        "macro_direction_only_oos_return_pct": (result.get("macro_ols_direction_only") or {}).get("net_return_pct"),
        "macro_cost_aware_oos_return_pct": (result.get("macro_ols_cost_aware") or {}).get("net_return_pct"),
        "macro_cost_aware_oos_changes": (result.get("macro_ols_cost_aware") or {}).get("position_changes"),
        "research_only": result.get("research_only"),
        "live_orders": result.get("live_orders"),
        "trade_ready": result.get("trade_ready"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
