import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("data/real_oos_audit/long_history_20261011")
COST = 0.0035
STEP = 14_400_000
CANDIDATES = {
    "BTCUSDT": [(20, 50), (45, 200)],
    "ETHUSDT": [(45, 100), (45, 200), (50, 200)],
}

def year(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc).year

def stamp(ts):
    return datetime.fromtimestamp(
        ts / 1000, timezone.utc
    ).strftime("%Y-%m-%d")

def load(symbol):
    rows = []
    with (ROOT / f"{symbol}_4h.jsonl").open() as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                rows.append({
                    "ts": int(r["ts"]),
                    "o": float(r["open"]),
                    "c": float(r["close"]),
                })
    rows.sort(key=lambda r: r["ts"])
    segs, cur = [], []
    for r in rows:
        if cur and r["ts"] - cur[-1]["ts"] != STEP:
            segs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        segs.append(cur)
    return segs

def ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    v = sum(values[:period]) / period
    out[period - 1] = v
    a = 2 / (period + 1)
    for i in range(period, len(values)):
        v = a * values[i] + (1 - a) * v
        out[i] = v
    return out

def analyze(seg, fast, slow):
    closes = [r["c"] for r in seg]
    f, s = ema(closes, fast), ema(closes, slow)
    trades = []
    entry = None
    start, end = None, None

    # Evaluate only the final holdout period.
    # Signals use completed candles and execute next-bar open.
    for i in range(1, len(seg) - 1):
        y = year(seg[i]["ts"])
        if y < 2025 or y > 2026:
            continue
        if f[i-1] is None or s[i-1] is None or f[i] is None or s[i] is None:
            continue
        up = f[i-1] <= s[i-1] and f[i] > s[i]
        down = f[i-1] >= s[i-1] and f[i] < s[i]
        px = seg[i+1]["o"]
        ts = seg[i+1]["ts"]

        if entry is not None and down:
            net = (px * (1-COST/2)) / (entry * (1+COST/2)) - 1
            trades.append({
                "entry": stamp(start), "exit": stamp(ts),
                "net": net * 100
            })
            entry, start = None, None
        elif entry is None and up:
            entry, start = px, ts

    # Close an open trade at the last eligible candle close.
    eligible = [r for r in seg if 2025 <= year(r["ts"]) <= 2026]
    if entry is not None and eligible:
        px = eligible[-1]["c"]
        net = (px * (1-COST/2)) / (entry * (1+COST/2)) - 1
        trades.append({
            "entry": stamp(start), "exit": stamp(eligible[-1]["ts"]),
            "net": net * 100
        })
    return trades

def compounded(values):
    equity = 1.0
    for v in values:
        equity *= 1 + v / 100
    return (equity - 1) * 100

def main():
    print("TRADE CONCENTRATION AUDIT | TEST 2025-2026")
    print("Round-trip cost=0.35%; research-only")
    for symbol, pairs in CANDIDATES.items():
        segs = load(symbol)
        print(f"\n===== {symbol} =====")
        for fast, slow in pairs:
            trades = []
            for seg in segs:
                trades.extend(analyze(seg, fast, slow))
            vals = [t["net"] for t in trades]
            winners = sorted(trades, key=lambda t: t["net"], reverse=True)
            print(f"\nEMA {fast}/{slow}: trades={len(trades)} "
                  f"net_compounded={compounded(vals):+.2f}%")
            if not trades:
                continue
            print(f"positive={sum(v > 0 for v in vals)} "
                  f"negative={sum(v < 0 for v in vals)} "
                  f"best={max(vals):+.2f}% worst={min(vals):+.2f}%")
            top3 = winners[:3]
            print("TOP 3:")
            for t in top3:
                print(f"  {t['entry']} -> {t['exit']} net={t['net']:+.2f}%")
            top3_sum = sum(t["net"] for t in top3)
            print(f"Top-3 arithmetic sum={top3_sum:+.2f}% "
                  "(diagnostic only, not compounded contribution)")
            print("ALL TRADES:")
            for t in sorted(trades, key=lambda t: t["entry"]):
                print(f"  {t['entry']} -> {t['exit']} net={t['net']:+.2f}%")

if __name__ == "__main__":
    main()
