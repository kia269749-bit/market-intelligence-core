import json
import math
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("data/real_oos_audit/long_history_20261011")
PAIRS = [(9,21),(12,26),(20,45),(20,50),(21,55),
         (45,100),(45,200),(50,200)]
ROUND_TRIP_COSTS = [0.001, 0.0035, 0.005]
PERIODS = [
    ("TRAIN", 2020, 2022),
    ("VALID", 2023, 2024),
    ("TEST", 2025, 2026),
]

def load_rows(symbol):
    p = ROOT / f"{symbol}_4h.jsonl"
    rows = []
    with p.open() as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rows.append({
                "ts": int(r["ts"]),
                "o": float(r["open"]),
                "h": float(r["high"]),
                "l": float(r["low"]),
                "c": float(r["close"]),
            })
    rows.sort(key=lambda x: x["ts"])
    return rows

def year_of(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc).year

def split_segments(rows):
    segs, cur = [], []
    for r in rows:
        if cur and r["ts"] - cur[-1]["ts"] != 14_400_000:
            if cur:
                segs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        segs.append(cur)
    return segs

def ema_values(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, len(values)):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev
    return out

def max_drawdown(returns):
    equity = peak = 1.0
    worst = 0.0
    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        if peak:
            worst = max(worst, 1 - equity / peak)
    return worst * 100

def stats(trades):
    if not trades:
        return (0, 0.0, 0.0, 0.0, 0.0, 0.0)
    eq = 1.0
    for t in trades:
        eq *= 1 + t
    wins = [x for x in trades if x > 0]
    gains = sum(wins)
    losses = -sum(x for x in trades if x < 0)
    pf = gains / losses if losses else (99.0 if gains else 0.0)
    return (len(trades), (eq - 1) * 100,
            len(wins) / len(trades) * 100,
            pf, max_drawdown(trades), sum(trades) / len(trades) * 100)

def run_period(rows, fast, slow, start_year, end_year, cost):
    closes = [r["c"] for r in rows]
    ef = ema_values(closes, fast)
    es = ema_values(closes, slow)
    trades = []
    pos = None

    # Only execute signals inside the evaluation period.
    # Indicators use prior historical closes, but no future values.
    eligible = [
        i for i, r in enumerate(rows)
        if start_year <= year_of(r["ts"]) <= end_year
    ]
    if len(eligible) < 2:
        return trades

    first, last = eligible[0], eligible[-1]
    for i in range(max(first + 1, 1), last + 1):
        prev = i - 1
        if ef[prev] is None or es[prev] is None or ef[i] is None or es[i] is None:
            continue

        # Signal is known only after the previous candle closes.
        cross_up = ef[prev] <= es[prev] and ef[i] > es[i]
        cross_down = ef[prev] >= es[prev] and ef[i] < es[i]

        # Execute today's signal at the next bar open.
        # Therefore signals at i are executed at i+1 open.
        if i + 1 > last:
            continue
        execution_price = rows[i + 1]["o"]

        if pos is not None and cross_down:
            ret = (execution_price * (1 - cost / 2)) / (
                pos * (1 + cost / 2)
            ) - 1
            trades.append(ret)
            pos = None
        elif pos is None and cross_up:
            pos = execution_price

    # Close any remaining position at the last period close.
    if pos is not None:
        exit_price = rows[last]["c"]
        ret = (exit_price * (1 - cost / 2)) / (
            pos * (1 + cost / 2)
        ) - 1
        trades.append(ret)
    return trades

def main():
    print("EMA CROSSOVER OOS TEST | research-only | no leverage")
    print("Execution: next-bar open | costs include entry and exit")
    print("Periods: TRAIN=2020-22, VALID=2023-24, TEST=2025-26")
    print("Metrics: compounded net return, win rate, PF, max DD")
    print("PF capped at 99 when there are wins but no losses")
    print()

    for symbol in ("BTCUSDT", "ETHUSDT"):
        rows = load_rows(symbol)
        segs = split_segments(rows)
        gaps = len(segs) - 1
        print(f"\n===== {symbol}: bars={len(rows)}, gaps={gaps} =====")
        for fast, slow in PAIRS:
            # Run each contiguous segment separately, preventing
            # indicator signals from crossing data gaps.
            for label, y0, y1 in PERIODS:
                for cost in ROUND_TRIP_COSTS:
                    all_trades = []
                    for seg in segs:
                        all_trades.extend(
                            run_period(seg, fast, slow, y0, y1, cost)
                        )
                    n, net, win, pf, dd, avg = stats(all_trades)
                    print(
                        f"{label:5s} EMA{fast:3d}/{slow:3d} "
                        f"cost={cost*100:.2f}% n={n:4d} "
                        f"net={net:+8.2f}% win={win:5.1f}% "
                        f"PF={pf:5.2f} DD={dd:6.2f}% "
                        f"avg_trade={avg:+.3f}%"
                    )

if __name__ == "__main__":
    main()
