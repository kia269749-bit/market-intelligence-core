
import json
import math
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/real_oos_audit/long_history_20261011")
STEP = 14_400_000
COSTS = (0.10, 0.35, 0.50)
N = 20
ATR_N = 14
WARMUP = 200

def date(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc)

def load(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]

def ema(vals, n):
    out = [None] * len(vals)
    if len(vals) < n:
        return out
    x = sum(vals[:n]) / n
    out[n-1] = x
    a = 2 / (n + 1)
    for i in range(n, len(vals)):
        x = a * vals[i] + (1-a) * x
        out[i] = x
    return out

def make_daily_filter(rows):
    closes = [float(r["close"]) for r in rows]
    e = ema(closes, 200)
    return [
        (int(r["ts"]) + 86_400_000,
         i >= 4 and e[i] is not None and e[i-4] is not None and e[i] > e[i-4])
        for i, r in enumerate(rows)
    ]

def trend_ok(filt, ts):
    times = [x[0] for x in filt]
    i = bisect_right(times, ts) - 1
    return i >= 0 and filt[i][1]

def split_segments(rows):
    out, cur = [], []
    for r in sorted(rows, key=lambda x: int(x["ts"])):
        b = {
            "ts": int(r["ts"]),
            "o": float(r["open"]), "h": float(r["high"]),
            "l": float(r["low"]), "c": float(r["close"]),
        }
        if cur and b["ts"] != cur[-1]["ts"] + STEP:
            out.append(cur)
            cur = []
        cur.append(b)
    if cur:
        out.append(cur)
    return out

def indicators(seg):
    trs = []
    for i, b in enumerate(seg):
        prev = seg[i-1]["c"] if i else b["c"]
        trs.append(max(b["h"]-b["l"], abs(b["h"]-prev), abs(b["l"]-prev)))
        b["atr"] = sum(trs[-ATR_N:]) / ATR_N if len(trs) >= ATR_N else None
        if i >= N:
            b["high20"] = max(x["h"] for x in seg[i-N:i])
            b["low20"] = min(x["l"] for x in seg[i-N:i])
        else:
            b["high20"] = b["low20"] = None
    return seg

def run(segments, filt, cost_pct, variant):
    trades = []
    cost = cost_pct / 100
    # Each trade pays half the stated round-trip cost on entry and exit.
    fee_factor = (1 - cost / 2) ** 2

    for raw in segments:
        seg = indicators([dict(x) for x in raw])
        pos = None
        for i, b in enumerate(seg):
            prev = seg[i-1] if i else None
            closed = False

            if pos is not None:
                exit_price = None
                if b["o"] <= pos["stop"]:
                    exit_price = b["o"]
                elif b["l"] <= pos["stop"]:
                    exit_price = pos["stop"]

                # Channel exit signal from the previously closed bar,
                # executed at current open.
                if exit_price is None and variant != "ATR_ONLY" and prev:
                    if prev["low20"] is not None and prev["c"] < prev["low20"]:
                        exit_price = b["o"]

                if exit_price is not None:
                    gross_factor = exit_price / pos["entry"]
                    trades.append({
                        "ts": pos["ts"],
                        "exit_ts": b["ts"],
                        "gross": (gross_factor - 1) * 100,
                        "net": (gross_factor * fee_factor - 1) * 100,
                    })
                    pos = None
                    closed = True

            if pos is None and not closed and prev is not None:
                signal = (
                    prev["high20"] is not None
                    and prev["c"] > prev["high20"]
                    and prev["atr"] is not None and prev["atr"] > 0
                )
                if variant != "NO_EMA" and not trend_ok(filt, b["ts"]):
                    signal = False

                if signal:
                    entry = b["o"]
                    # Identical initial risk rule for all variants.
                    stop = max(entry - 2 * prev["atr"], entry * 0.95)
                    pos = {"ts": b["ts"], "entry": entry, "stop": stop, "high": entry}

                    # Conservative same-bar entry stop handling.
                    if b["o"] <= stop or b["l"] <= stop:
                        px = b["o"] if b["o"] <= stop else stop
                        ratio = px / entry
                        trades.append({
                            "ts": b["ts"], "exit_ts": b["ts"],
                            "gross": (ratio-1)*100,
                            "net": (ratio*fee_factor-1)*100,
                        })
                        pos = None
                        continue

            if pos is not None and b["atr"] is not None:
                pos["high"] = max(pos["high"], b["h"])
                trail = pos["high"] - 2 * b["atr"]
                pos["stop"] = max(pos["stop"], trail, pos["entry"] * 0.95)

        if pos is not None:
            px = seg[-1]["c"]
            ratio = px / pos["entry"]
            trades.append({
                "ts": pos["ts"], "exit_ts": seg[-1]["ts"],
                "gross": (ratio-1)*100,
                "net": (ratio*fee_factor-1)*100,
            })

    return sorted(trades, key=lambda x: x["ts"])

def bucket(ts):
    y = date(ts).year
    if y <= 2022:
        return "TRAIN_2020_2022"
    if y <= 2024:
        return "VALID_2023_2024"
    return "PREVIOUSLY_VIEWED_TEST_2025_2026"

def summarize(trades):
    equity = peak = 1.0
    dd = 0.0
    wins = losses = 0
    gp = gl = 0.0
    for t in trades:
        r = t["net"] / 100
        equity *= max(0.000001, 1+r)
        peak = max(peak, equity)
        dd = max(dd, (peak-equity)/peak)
        if r > 0:
            wins += 1
            gp += r
        elif r < 0:
            losses += 1
            gl += -r
    pf = gp/gl if gl else (math.inf if gp else 0)
    return len(trades), (equity-1)*100, wins/max(1,len(trades))*100, pf, dd*100

def main():
    variants = ("ATR_ONLY", "CHANNEL_EXIT", "NO_EMA")
    boundaries = (
        ("TRAIN_to_VALID_2023", int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)),
        ("VALID_to_TEST_2025", int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)),
    )
    print("Research-only comparison. No live orders.")
    print("NO_EMA means no daily trend filter; all other entry/stop rules stay the same.")
    print("Channel exit uses previous closed bar's 20-bar low, exits at next open.")
    print("All trades pay modeled round-trip costs; slippage/funding are not included.")
    print("Use TRAIN/VALID for selection. The 2025-2026 period was already inspected.\n")

    for sym in ("BTCUSDT", "ETHUSDT"):
        p4, pd = ROOT/f"{sym}_4h.jsonl", ROOT/f"{sym}_1d.jsonl"
        if not p4.exists() or not pd.exists():
            raise SystemExit(f"Missing data for {sym}")
        segments = split_segments(load(p4))
        filt = make_daily_filter(load(pd))
        print(f"\n========== {sym} | segments={[len(s) for s in segments]} ==========")

        for cost in COSTS:
            print(f"\nROUND_TRIP_COST={cost:.2f}%")
            for v in variants:
                trades = run(segments, filt, cost, v)
                print(f"  {v}")
                for boundary_name, boundary_ts in boundaries:
                    crossing = sum(
                        1 for t in trades
                        if t["ts"] < boundary_ts <= t["exit_ts"]
                    )
                    print(f"    {boundary_name}: crossing_trades={crossing}")
                for label in ("TRAIN_2020_2022", "VALID_2023_2024", "PREVIOUSLY_VIEWED_TEST_2025_2026"):
                    part = [t for t in trades if bucket(t["ts"]) == label]
                    n, net, win, pf, dd = summarize(part)
                    pf_s = "inf" if math.isinf(pf) else f"{pf:.2f}"
                    print(
                        f"    {label}: n={n} net_compounded={net:+.2f}% "
                        f"win={win:.1f}% PF={pf_s} DD={dd:.2f}%"
                    )

if __name__ == "__main__":
    main()
