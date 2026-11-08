import csv
import json
import math
from pathlib import Path

DATA = Path("data/real_oos_audit/multitimeframe_20261011")
OUT = Path("data/real_oos_audit/mtf_200_results_v2")
COSTS = (0.0010, 0.0035)  # round trip: 0.10% and 0.35%

HORIZONS = {
    "5m": [3, 6, 12],
    "15m": [2, 4, 8],
    "1h": [2, 3, 6],
    "4h": [2, 3, 5],
}

def sma(a, w):
    p = [0.0]
    for x in a:
        p.append(p[-1] + x)
    out = [None] * len(a)
    for i in range(w - 1, len(a)):
        out[i] = (p[i + 1] - p[i + 1 - w]) / w
    return out

def rolling_extreme(a, w, high=True):
    out = [None] * len(a)
    for i in range(w - 1, len(a)):
        part = a[i - w + 1:i + 1]
        out[i] = max(part) if high else min(part)
    return out

def rsi(close, w):
    out = [None] * len(close)
    for i in range(w, len(close)):
        gains = losses = 0.0
        for j in range(i - w + 1, i + 1):
            d = close[j] - close[j - 1]
            if d > 0:
                gains += d
            elif d < 0:
                losses -= d
        if losses == 0:
            out[i] = 100.0 if gains else 50.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + gains / losses)
    return out

def make_rules():
    rules = []

    def add(family, params):
        for p in params:
            rules.append({"family": family, **p})

    add("momentum", [
        {"lookback": w, "threshold": t}
        for w in [3, 5, 8, 12, 16]
        for t in [0.0, 0.001, 0.002, 0.004]
    ])
    add("ma_trend", [
        {"fast": f, "slow": s}
        for f in [3, 5, 8, 10, 12]
        for s in [20, 30, 40, 50]
    ])
    add("breakout", [
        {"window": w, "buffer": b}
        for w in [5, 8, 12, 20, 30]
        for b in [0.0, 0.0005, 0.001, 0.002]
    ])
    add("rsi_reversal", [
        {"period": w, "level": l}
        for w in [5, 7, 10, 14, 21]
        for l in [20, 25, 30, 35]
    ])
    add("rsi_momentum", [
        {"period": w, "level": l}
        for w in [5, 7, 10, 14, 21]
        for l in [45, 50, 55, 60]
    ])
    add("mean_reversion", [
        {"window": w, "deviation": d}
        for w in [10, 20, 30, 40, 50]
        for d in [0.002, 0.004, 0.006, 0.008]
    ])
    add("candle_body", [
        {"body_ratio": b, "trend_window": w}
        for b in [0.4, 0.5, 0.6, 0.7, 0.8]
        for w in [10, 20, 30, 50]
    ])
    add("trend_pullback", [
        {"fast": f, "slow": s}
        for f in [5, 8, 10, 12, 15]
        for s in [20, 30, 40, 50]
    ])
    add("volume_breakout", [
        {"window": w, "volume_ratio": v}
        for w in [5, 8, 12, 20, 30]
        for v in [1.2, 1.5, 2.0, 2.5]
    ])
    add("range_momentum", [
        {"lookback": w, "range_multiple": m}
        for w in [3, 5, 8, 12, 16]
        for m in [0.5, 0.75, 1.0, 1.25]
    ])

    assert len(rules) == 200, len(rules)
    for i, rule in enumerate(rules):
        rule["id"] = f"P{i+1:03d}"
        rule["horizon_slot"] = i % 3
    return rules

def load_bars(path):
    bars = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    if len(bars) < 300:
        raise ValueError(f"Too few bars: {path}")
    ts = [b["ts"] for b in bars]
    if ts != sorted(set(ts)):
        raise ValueError(f"Duplicate or unordered timestamps: {path}")
    for b in bars:
        o, h, l, c, v = (b[k] for k in ("open", "high", "low", "close", "volume"))
        if min(o, h, l, c) <= 0 or v < 0 or h < max(o, l, c) or l > min(o, h, c):
            raise ValueError(f"Invalid OHLCV: {path}")
    return bars

def features(bars):
    o = [b["open"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    v = [b["volume"] for b in bars]
    n = len(c)

    windows = {3, 5, 7, 8, 10, 12, 14, 15, 16, 20, 21, 24, 30, 40, 50}
    ma = {w: sma(c, w) for w in windows}
    volma = {w: sma(v, w) for w in [5, 8, 12, 20, 30]}
    rsis = {w: rsi(c, w) for w in [5, 7, 10, 14, 21]}
    hh = {w: rolling_extreme(h, w, True) for w in [5, 8, 12, 20, 30]}
    ll = {w: rolling_extreme(l, w, False) for w in [5, 8, 12, 20, 30]}

    tr = [h[0] - l[0]]
    for i in range(1, n):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1])))
    atr = {w: sma(tr, w) for w in [3, 5, 8, 12, 16]}

    body_ratio = []
    for i in range(n):
        rng = h[i] - l[i]
        body_ratio.append(abs(c[i] - o[i]) / rng if rng else 0.0)

    return locals()

def signal(rule, i, f):
    c, o, h, l, v = f["c"], f["o"], f["h"], f["l"], f["v"]
    ma, rsis, hh, ll = f["ma"], f["rsis"], f["hh"], f["ll"]
    volma, atr = f["volma"], f["atr"]
    family = rule["family"]

    if family == "momentum":
        w, t = rule["lookback"], rule["threshold"]
        if i < w or c[i-w] == 0:
            return 0
        r = c[i] / c[i-w] - 1
        return 1 if r > t else -1 if r < -t else 0

    if family == "ma_trend":
        a, b = ma[rule["fast"]][i], ma[rule["slow"]][i]
        return 1 if a is not None and b is not None and a > b else -1 if a is not None and b is not None and a < b else 0

    if family == "breakout":
        w, b = rule["window"], rule["buffer"]
        if i < w or hh[w][i-1] is None:
            return 0
        return 1 if c[i] > hh[w][i-1] * (1+b) else -1 if c[i] < ll[w][i-1] * (1-b) else 0

    if family == "rsi_reversal":
        x = rsis[rule["period"]][i]
        if x is None:
            return 0
        return 1 if x < rule["level"] else -1 if x > 100-rule["level"] else 0

    if family == "rsi_momentum":
        x = rsis[rule["period"]][i]
        if x is None:
            return 0
        return 1 if x > rule["level"] else -1 if x < 100-rule["level"] else 0

    if family == "mean_reversion":
        w = rule["window"]
        avg = ma[w][i]
        if avg is None or avg == 0:
            return 0
        d = c[i] / avg - 1
        return 1 if d < -rule["deviation"] else -1 if d > rule["deviation"] else 0

    if family == "candle_body":
        w = rule["trend_window"]
        avg = ma[w][i]
        if avg is None or f["body_ratio"][i] < rule["body_ratio"]:
            return 0
        direction = 1 if c[i] > o[i] else -1 if c[i] < o[i] else 0
        if direction == 1 and c[i] > avg:
            return 1
        if direction == -1 and c[i] < avg:
            return -1
        return 0

    if family == "trend_pullback":
        fast, slow = ma[rule["fast"]][i], ma[rule["slow"]][i]
        if fast is None or slow is None or i < 3:
            return 0
        if fast > slow and c[i] < fast and c[i] > slow and c[i] > c[i-3]:
            return 1
        if fast < slow and c[i] > fast and c[i] < slow and c[i] < c[i-3]:
            return -1
        return 0

    if family == "volume_breakout":
        w = rule["window"]
        avg = volma[w][i]
        if avg is None or avg <= 0 or v[i] < avg * rule["volume_ratio"] or i < w:
            return 0
        return 1 if c[i] > hh[w][i-1] else -1 if c[i] < ll[w][i-1] else 0

    if family == "range_momentum":
        w = rule["lookback"]
        a = atr[w][i]
        if a is None or c[i-w] == 0:
            return 0
        move = c[i] - c[i-w]
        threshold = a * rule["range_multiple"]
        return 1 if move > threshold else -1 if move < -threshold else 0

    return 0

def stats(trades):
    if not trades:
        return {"n": 0, "avg_net_pct": None, "win_pct": None,
                "pf": None, "max_dd_pct": None}
    vals = [x for x in trades]
    wins = sum(x for x in vals if x > 0)
    losses = -sum(x for x in vals if x < 0)
    eq = peak = 0.0
    maxdd = 0.0
    for x in vals:
        eq += x
        peak = max(peak, eq)
        maxdd = max(maxdd, peak - eq)
    return {
        "n": len(vals),
        "avg_net_pct": 100 * sum(vals) / len(vals),
        "win_pct": 100 * sum(x > 0 for x in vals) / len(vals),
        "pf": wins / losses if losses else (999.0 if wins else 0.0),
        "max_dd_pct": 100 * maxdd,
    }

def evaluate(rule, sigs, bars, start, end, horizon, cost):
    close = [b["close"] for b in bars]
    op = [b["open"] for b in bars]
    trades = []
    next_entry = start + 1
    i = max(start, 1)
    while i < end - 1:
        direction = sigs[i]
        entry = i + 1
        exit_i = entry + horizon - 1
        if direction and entry >= next_entry and exit_i < end:
            if op[entry] > 0:
                gross = direction * (close[exit_i] / op[entry] - 1)
                trades.append(gross - cost)
                next_entry = exit_i + 1
                i = next_entry
                continue
        i += 1
    return stats(trades)

def main():
    if OUT.exists():
        raise FileExistsError(f"Results directory already exists: {OUT}")
    rules = make_rules()
    print("RESEARCH ONLY | LIVE ORDERS = FALSE")
    print(f"Rules per timeframe: {len(rules)}")
    print("Selection uses validation only; test is not used for ranking.")
    OUT.mkdir(parents=True)

    for symbol in ("BTCUSDT", "ETHUSDT"):
        for tf in ("5m", "15m", "1h", "4h"):
            path = DATA / f"{symbol}_{tf}.jsonl"
            bars = load_bars(path)
            f = features(bars)
            n = len(bars)
            a, b = int(n * 0.60), int(n * 0.80)
            horizons = HORIZONS[tf]
            all_results = []

            print(f"\n{symbol} {tf}: bars={n}, split={a}/{b}/{n}")
            for rule in rules:
                horizon = horizons[rule["horizon_slot"]]
                sigs = [signal(rule, i, f) for i in range(n)]
                row = {
                    "symbol": symbol, "timeframe": tf,
                    "id": rule["id"], "family": rule["family"],
                    "parameters": json.dumps(
                        {k:v for k,v in rule.items()
                         if k not in ("id", "family", "horizon_slot")},
                        sort_keys=True
                    ),
                    "horizon_bars": horizon,
                }
                for cost in COSTS:
                    tag = f"cost_{cost:.4f}"
                    for split, lo, hi in (
                        ("train", 0, a), ("validation", a, b), ("test", b, n)
                    ):
                        result = evaluate(rule, sigs, bars, lo, hi, horizon, cost)
                        for key, value in result.items():
                            row[f"{split}_{tag}_{key}"] = value
                all_results.append(row)

            # Rank only on validation at 0.10% cost.
            all_results.sort(key=lambda r: (
                r["validation_cost_0.0010_avg_net_pct"] is not None,
                r["validation_cost_0.0010_avg_net_pct"] or -999,
                r["validation_cost_0.0010_pf"] or 0,
                r["validation_cost_0.0010_n"]
            ), reverse=True)

            file = OUT / f"{symbol}_{tf}_all200.csv"
            with file.open("x", newline="", encoding="utf-8") as fcsv:
                writer = csv.DictWriter(fcsv, fieldnames=list(all_results[0]))
                writer.writeheader()
                writer.writerows(all_results)

            top = all_results[:10]
            topfile = OUT / f"{symbol}_{tf}_top10_validation.csv"
            with topfile.open("x", newline="", encoding="utf-8") as fcsv:
                writer = csv.DictWriter(fcsv, fieldnames=list(top[0]))
                writer.writeheader()
                writer.writerows(top)

            print("Top 10 by validation, cost 0.10%:")
            for r in top:
                print(
                    f"{r['id']} {r['family']:17} H={r['horizon_bars']:2} "
                    f"val_n={r['validation_cost_0.0010_n']:3} "
                    f"val_avg={r['validation_cost_0.0010_avg_net_pct']}% "
                    f"val_PF={r['validation_cost_0.0010_pf']} | "
                    f"test_n={r['test_cost_0.0010_n']:3} "
                    f"test_avg={r['test_cost_0.0010_avg_net_pct']}% "
                    f"test_PF={r['test_cost_0.0010_pf']}"
                )

    summary = OUT / "README.txt"
    summary.write_text(
        "Research-only pattern sweep.\n"
        "200 rule configurations per asset/timeframe.\n"
        "Ranking uses validation results at 0.10% round-trip cost.\n"
        "0.35% cost sensitivity is included in each CSV.\n"
        "The test split is reported only for the validation-selected top 10.\n"
        "These results are exploratory, not proof of profitability.\n",
        encoding="utf-8"
    )
    print("\nDONE. Results:", OUT)
    print("Source project modules were not edited.")
    print("LIVE ORDERS = FALSE")

if __name__ == "__main__":
    main()
