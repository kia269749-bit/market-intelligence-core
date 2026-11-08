
import json
import math
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/real_oos_audit/long_history_20261011")
COSTS = (0.10, 0.35, 0.50)  # درصد رفت‌وبرگشت
START = 20
ATR_N = 14
DONCHIAN_N = 20
INITIAL_STOP_ATR = 2.0
CATASTROPHE_STOP = 0.05

def dt(ts):
    return datetime.fromtimestamp(ts / 1000, timezone.utc)

def load(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1 - alpha)
        out[i] = prev
    return out

def daily_trend(daily):
    closes = [float(x["close"]) for x in daily]
    e = ema(closes, 200)
    # برای روز جاری فقط از آخرین کندل روزانه‌ای استفاده می‌کنیم
    # که در لحظهٔ بازشدن کندل 4h کاملاً بسته شده است.
    result = []
    for i in range(len(daily)):
        rising = (
            i >= 4 and e[i] is not None and e[i - 4] is not None
            and e[i] > e[i - 4]
        )
        result.append((int(daily[i]["ts"]) + 86_400_000, rising))
    return result

def trend_at(daily_filter, entry_ts):
    closes_at = [x[0] for x in daily_filter]
    i = bisect_right(closes_at, entry_ts) - 1
    return i >= 0 and daily_filter[i][1]

def prepare_segments(rows):
    bars = []
    for r in rows:
        bars.append({
            "ts": int(r["ts"]),
            "o": float(r["open"]),
            "h": float(r["high"]),
            "l": float(r["low"]),
            "c": float(r["close"]),
        })
    bars.sort(key=lambda x: x["ts"])
    segments = []
    cur = []
    step = 14_400_000
    for b in bars:
        if cur and b["ts"] != cur[-1]["ts"] + step:
            segments.append(cur)
            cur = []
        cur.append(b)
    if cur:
        segments.append(cur)
    return segments

def add_indicators(seg):
    trs, atrs = [], [None] * len(seg)
    for i, b in enumerate(seg):
        if i == 0:
            tr = b["h"] - b["l"]
        else:
            prev = seg[i - 1]["c"]
            tr = max(b["h"] - b["l"], abs(b["h"] - prev), abs(b["l"] - prev))
        trs.append(tr)
        if i >= ATR_N - 1:
            atrs[i] = sum(trs[i - ATR_N + 1:i + 1]) / ATR_N
    for i, b in enumerate(seg):
        b["atr"] = atrs[i]
        b["prior_high"] = (
            max(x["h"] for x in seg[i - DONCHIAN_N:i])
            if i >= DONCHIAN_N else None
        )
    return seg

def backtest(segments, daily_filter, cost_pct):
    trades = []
    for raw_seg in segments:
        seg = add_indicators([dict(b) for b in raw_seg])
        pos = None
        last_exit_i = -2

        for i, b in enumerate(seg):
            exited_now = False

            # stop hiện có đã được xác định từ cuối nến trước
            if pos is not None:
                stop = pos["stop"]
                if b["o"] <= stop:
                    exit_price = b["o"]  # xử lý bảo thủ khi gap qua stop
                elif b["l"] <= stop:
                    exit_price = stop
                else:
                    exit_price = None

                if exit_price is not None:
                    gross = exit_price / pos["entry"] - 1
                    net_factor = (1 + gross) * (1 - cost_pct / 100)
                    trades.append({
                        "entry_ts": pos["entry_ts"],
                        "exit_ts": b["ts"],
                        "gross_pct": gross * 100,
                        "net_pct": (net_factor - 1) * 100,
                        "entry": pos["entry"],
                        "exit": exit_price,
                    })
                    pos = None
                    last_exit_i = i
                    exited_now = True

            # سیگنال شکست فقط از اطلاعات کندل بسته‌شدهٔ قبلی استفاده می‌کند
            if pos is None and not exited_now and i > 0:
                prev = seg[i - 1]
                if (
                    prev["prior_high"] is not None
                    and prev["c"] > prev["prior_high"]
                    and prev["atr"] is not None
                    and prev["atr"] > 0
                    and trend_at(daily_filter, b["ts"])
                    and i - last_exit_i > 1
                ):
                    entry = b["o"]
                    initial_stop = max(
                        entry - INITIAL_STOP_ATR * prev["atr"],
                        entry * (1 - CATASTROPHE_STOP),
                    )
                    pos = {
                        "entry_ts": b["ts"],
                        "entry": entry,
                        "stop": initial_stop,
                        "highest": entry,
                    }

                    # کندل ورود نیز بررسی می‌شود؛ از برخورد به stop صرف‌نظر نمی‌کنیم.
                    if b["o"] <= pos["stop"] or b["l"] <= pos["stop"]:
                        exit_price = b["o"] if b["o"] <= pos["stop"] else pos["stop"]
                        gross = exit_price / entry - 1
                        net_factor = (1 + gross) * (1 - cost_pct / 100)
                        trades.append({
                            "entry_ts": b["ts"],
                            "exit_ts": b["ts"],
                            "gross_pct": gross * 100,
                            "net_pct": (net_factor - 1) * 100,
                            "entry": entry,
                            "exit": exit_price,
                        })
                        pos = None
                        last_exit_i = i
                        continue

            # به‌روزرسانی trailing stop برای کندل بعدی، نه کندل جاری
            if pos is not None and b["atr"] is not None:
                pos["highest"] = max(pos["highest"], b["h"])
                trailing = pos["highest"] - INITIAL_STOP_ATR * b["atr"]
                catastrophe = pos["entry"] * (1 - CATASTROPHE_STOP)
                pos["stop"] = max(pos["stop"], trailing, catastrophe)

        # اگر پوزیشن تا انتهای یک قطعه باز بماند، در آخرین بسته‌شدن همان قطعه بسته می‌شود.
        if pos is not None:
            last = seg[-1]
            gross = last["c"] / pos["entry"] - 1
            net_factor = (1 + gross) * (1 - cost_pct / 100)
            trades.append({
                "entry_ts": pos["entry_ts"],
                "exit_ts": last["ts"],
                "gross_pct": gross * 100,
                "net_pct": (net_factor - 1) * 100,
                "entry": pos["entry"],
                "exit": last["c"],
            })
    return sorted(trades, key=lambda t: t["entry_ts"])

def stats(trades):
    eq = peak = 1.0
    max_dd = 0.0
    wins = 0
    gross_profit = gross_loss = 0.0
    for t in trades:
        r = t["net_pct"] / 100
        eq *= max(0.000001, 1 + r)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak)
        if r > 0:
            wins += 1
            gross_profit += r
        elif r < 0:
            gross_loss += -r
    return {
        "n": len(trades),
        "net": (eq - 1) * 100,
        "win": wins / len(trades) * 100 if trades else 0,
        "pf": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0),
        "dd": max_dd * 100,
    }

def period(ts):
    y = dt(ts).year
    if y <= 2022:
        return "TRAIN_2020_2022"
    if y <= 2024:
        return "VALID_2023_2024"
    return "TEST_2025_2026"

def main():
    print("DONCHIAN LONG-ONLY | NO LEVERAGE | NO PYRAMIDING")
    print("Entry: next 4h open after prior close breaks previous 20-bar high")
    print("Trend: last fully closed daily EMA200 above its value 4 days earlier")
    print("Stop: 2x ATR(14), with 5% catastrophe floor; stop gaps use open price")
    print("Costs: round-trip haircut; funding/slippage beyond this are not modeled")
    print("Research only. Not a live trading signal.\n")

    for symbol in ("BTCUSDT", "ETHUSDT"):
        p4 = ROOT / f"{symbol}_4h.jsonl"
        pd = ROOT / f"{symbol}_1d.jsonl"
        if not p4.exists() or not pd.exists():
            raise SystemExit(f"Missing input for {symbol}")
        rows4 = load(p4)
        rowsd = load(pd)
        dfilter = daily_trend(rowsd)
        segments = prepare_segments(rows4)

        print(f"\n========== {symbol} ==========")
        print(f"4h bars={len(rows4)} | segments={len(segments)} | daily bars={len(rowsd)}")
        print("segment lengths:", [len(s) for s in segments])

        all_bars = sorted(
            (b for s in segments for b in s), key=lambda x: x["ts"]
        )
        if len(all_bars) < 100:
            print("Insufficient bars")
            continue

        for cost in COSTS:
            trades = backtest(segments, dfilter, cost)
            print(f"\nCOST_ROUNDTRIP={cost:.2f}%")
            for label in ("TRAIN_2020_2022", "VALID_2023_2024", "TEST_2025_2026"):
                subset = [t for t in trades if period(t["entry_ts"]) == label]
                s = stats(subset)
                pf = "inf" if math.isinf(s["pf"]) else f'{s["pf"]:.2f}'
                print(
                    f"{label}: trades={s['n']} compounded_net={s['net']:+.2f}% "
                    f"win_rate={s['win']:.1f}% PF={pf} trade_sequence_DD={s['dd']:.2f}%"
                )

        # Benchmark سادهٔ نگهداری در کل دوره و در دورهٔ آزمون
        first = all_bars[0]
        last = all_bars[-1]
        print(
            f"BUY_HOLD_FULL_PERIOD gross={(last['c']/first['o']-1)*100:+.2f}% "
            f"from={dt(first['ts']).date()} to={dt(last['ts']).date()}"
        )
        test_bars = [b for b in all_bars if dt(b["ts"]).year >= 2025]
        if len(test_bars) > 1:
            print(
                f"BUY_HOLD_TEST gross={(test_bars[-1]['c']/test_bars[0]['o']-1)*100:+.2f}% "
                f"from={dt(test_bars[0]['ts']).date()} to={dt(test_bars[-1]['ts']).date()}"
            )

    print("\nNOTE: This is a first-pass backtest. Review assumptions and results before any conclusions.")

if __name__ == "__main__":
    main()
