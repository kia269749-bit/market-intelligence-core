import json
import math
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/real_oos_audit"
MULTI = BASE / "multitimeframe_20261011"
LONG = BASE / "long_history_20261011"
OUT = BASE / "adaptive_supertrend_algoalpha_20261011.csv"

ATR_LEN = 10
FACTOR = 3.0
TRAINING_WINDOW = 100
COSTS = (0.0010, 0.0035)


def load(path):
    rows = []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            try:
                x = json.loads(line)
                r = {k: float(x[k]) for k in
                     ("open", "high", "low", "close")}
                r["ts"] = int(x["ts"])
                if not all(math.isfinite(r[k]) and r[k] > 0
                           for k in ("open", "high", "low", "close")):
                    continue
                if (r["high"] < max(r["open"], r["close"], r["low"])
                        or r["low"] > min(r["open"], r["close"])):
                    continue
                rows.append(r)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue

    rows.sort(key=lambda x: x["ts"])
    unique = []
    for r in rows:
        if not unique or r["ts"] != unique[-1]["ts"]:
            unique.append(r)
    return unique


def true_ranges(rows):
    out = []
    for i, r in enumerate(rows):
        if i == 0:
            out.append(r["high"] - r["low"])
        else:
            pc = rows[i - 1]["close"]
            out.append(max(
                r["high"] - r["low"],
                abs(r["high"] - pc),
                abs(r["low"] - pc),
            ))
    return out


def wilder_atr(rows, period):
    tr = true_ranges(rows)
    atr = [None] * len(rows)
    if len(rows) < period:
        return atr
    atr[period - 1] = sum(tr[:period]) / period
    for i in range(period, len(rows)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def kmeans_atr_centroid(values, max_iter=100):
    """Bounded 3-cluster approximation of AlgoAlpha's ATR clustering."""
    if not values:
        return None

    lo, hi = min(values), max(values)
    if hi - lo <= 1e-12:
        return sum(values) / len(values)

    centers = [
        lo + (hi - lo) * 0.75,
        lo + (hi - lo) * 0.50,
        lo + (hi - lo) * 0.25,
    ]

    for _ in range(max_iter):
        groups = [[], [], []]
        for value in values:
            j = min(range(3), key=lambda k: abs(value - centers[k]))
            groups[j].append(value)

        updated = [
            sum(g) / len(g) if g else centers[i]
            for i, g in enumerate(groups)
        ]

        delta = max(abs(updated[i] - centers[i]) for i in range(3))
        centers = updated
        if delta < 1e-10:
            break

    return min(centers, key=lambda c: abs(c - values[-1]))


def calc_supertrend(rows, adaptive):
    n = len(rows)
    atr = wilder_atr(rows, ATR_LEN)
    used_atr = [None] * n

    for i in range(n):
        if atr[i] is None:
            continue
        if not adaptive:
            used_atr[i] = atr[i]
            continue

        # The current ATR uses only the current and preceding bars.
        window = [
            atr[j] for j in range(max(0, i - TRAINING_WINDOW + 1), i + 1)
            if atr[j] is not None
        ]
        if len(window) >= min(ATR_LEN, TRAINING_WINDOW):
            used_atr[i] = kmeans_atr_centroid(window)

    direction = [None] * n
    upper = [None] * n
    lower = [None] * n

    for i, r in enumerate(rows):
        a = used_atr[i]
        if a is None:
            continue

        mid = (r["high"] + r["low"]) / 2
        bu = mid + FACTOR * a
        bl = mid - FACTOR * a

        if i == 0 or upper[i - 1] is None or lower[i - 1] is None:
            upper[i], lower[i] = bu, bl
            direction[i] = 1 if r["close"] >= mid else -1
            continue

        pu, pl = upper[i - 1], lower[i - 1]
        pc = rows[i - 1]["close"]

        upper[i] = bu if bu < pu or pc > pu else pu
        lower[i] = bl if bl > pl or pc < pl else pl

        pd = direction[i - 1]
        if pd == -1:
            direction[i] = 1 if r["close"] > upper[i] else -1
        else:
            direction[i] = -1 if r["close"] < lower[i] else 1

    return direction


def evaluate(rows, direction, start, end, cost, interval):
    # Long-only, same execution convention as the existing baseline.
    # Signal from the previous candle; execution at the next candle open.
    trades = []
    pos = False
    entry = None

    for i in range(max(start + 1, 1), end):
        prev, cur = rows[i - 1], rows[i]
        gap = cur["ts"] - prev["ts"] > interval * 1.5

        if gap and pos and entry is not None:
            trades.append(cur["open"] / entry - 1 - cost)
            pos, entry = False, None

        d = direction[i - 1]
        if d is None:
            continue

        if not pos and d == 1:
            pos, entry = True, cur["open"]
        elif pos and d == -1 and entry is not None:
            trades.append(cur["open"] / entry - 1 - cost)
            pos, entry = False, None

    if pos and entry is not None and end > start:
        trades.append(rows[end - 1]["close"] / entry - 1 - cost)

    equity = peak = 1.0
    maxdd = 0.0
    for ret in trades:
        equity *= max(0.000001, 1 + ret)
        peak = max(peak, equity)
        maxdd = max(maxdd, (peak - equity) / peak)

    wins = [x for x in trades if x > 0]
    losses = [-x for x in trades if x < 0]
    pf = sum(wins) / sum(losses) if losses else (999 if wins else 0)
    bh = rows[end - 1]["close"] / rows[start]["open"] - 1 if end - start > 1 else 0

    return [
        len(trades),
        round((equity - 1) * 100, 3),
        round(sum(trades) / len(trades) * 100, 3) if trades else 0,
        round(len(wins) / len(trades) * 100, 1) if trades else 0,
        round(pf, 3),
        round(maxdd * 100, 2),
        round(bh * 100, 3),
    ]


def main():
    datasets = []
    for sym in ("BTCUSDT", "ETHUSDT"):
        for tf, ms in (
            ("5m", 300000), ("15m", 900000),
            ("1h", 3600000), ("4h", 14400000),
        ):
            datasets.append((sym, tf, "multitimeframe", MULTI / f"{sym}_{tf}.jsonl", ms))

        # Additional longer 4h history, evaluated separately.
        datasets.append((sym, "4h", "long_history", LONG / f"{sym}_4h.jsonl", 14400000))

    header = [
        "symbol", "tf", "dataset", "part", "method", "atr_len",
        "factor", "training_window", "cost", "trades", "net_pct",
        "avg_trade_pct", "win_pct", "pf", "closed_trade_maxdd_pct",
        "buyhold_pct",
    ]

    print("Research-only AlgoAlpha Adaptive SuperTrend")
    print("No network, service control, or trading orders.")
    print("Files found:")
    for sym, tf, label, path, ms in datasets:
        if path.exists():
            print(f"  {sym} {tf} {label}: {path}")

    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        written = 0

        for sym, tf, label, path, ms in datasets:
            if not path.exists():
                continue

            rows = load(path)
            n = len(rows)
            if n < 150:
                print("SKIP_TOO_FEW_ROWS", sym, tf, label, n)
                continue

            gaps = sum(
                rows[i]["ts"] - rows[i - 1]["ts"] > ms * 1.5
                for i in range(1, n)
            )
            if gaps:
                print("SKIP_GAPS", sym, tf, label, "gaps=", gaps)
                continue

            a, b = int(n * 0.60), int(n * 0.80)
            methods = {
                "standard": calc_supertrend(rows, adaptive=False),
                "adaptive_kmeans": calc_supertrend(rows, adaptive=True),
            }

            for method, direction in methods.items():
                for part, lo, hi in (
                    ("TRAIN", 0, a), ("VALID", a, b), ("TEST", b, n)
                ):
                    for cost in COSTS:
                        result = evaluate(rows, direction, lo, hi, cost, ms)
                        w.writerow([
                            sym, tf, label, part, method, ATR_LEN, FACTOR,
                            TRAINING_WINDOW, cost
                        ] + result)
                        written += 1

            print(f"OK {sym} {tf} {label}: rows={n}, "
                  f"TRAIN={a}, VALID={b-a}, TEST={n-b}")

    print()
    print("===== TEST: COST 0.35%, STANDARD vs ADAPTIVE =====")
    print("CSV:", OUT)
    print("Rows written:", written)
    print("Caution: Python approximation, not exact Pine parity.")
    print("Costs are estimated; slippage and funding are not modeled.")
    print("Max drawdown is closed-trade drawdown, not intratrade drawdown.")


if __name__ == "__main__":
    main()
