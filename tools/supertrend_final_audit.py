import csv
import json
import math
import random
import statistics
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(".")
OHLC_FILE = ROOT / "data/real_oos_audit/BTCUSDT_1h_OHLC_20261011.jsonl"
CSV_FILES = [
    ROOT / "data/real_oos_audit/supertrend_oos_20261011.csv",
    ROOT / "data/real_oos_audit/adaptive_supertrend_algoalpha_20261011.csv",
]

CAPITAL = 500.0
ATR_LENGTH = 10
ST_MULTIPLIER = 3.0
COSTS = {
    "BASE_0.15%": 0.0015,
    "STRICT_0.45%": 0.0045,
}
RANDOM_SEED = 20261030
EXPECTED_INTERVAL_MS = 60 * 60 * 1000

def pct(x): return f"{x:+.4f}%"
def usd(x): return f"${x:+.2f}"
def timestamp_text(ts): return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
def safe_float(value):
    x = float(value)
    if not math.isfinite(x): raise ValueError(f"Non-finite: {value}")
    return x

def max_drawdown(equity_curve):
    if not equity_curve: return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            dd = (value / peak - 1.0) * 100.0
            worst = min(worst, dd)
    return worst

def load_ohlc(path):
    if not path.exists(): raise FileNotFoundError(path)
    bars = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip(): continue
            row = json.loads(line)
            bar = {
                "ts": int(row["ts"]),
                "open": safe_float(row["open"]),
                "high": safe_float(row["high"]),
                "low": safe_float(row["low"]),
                "close": safe_float(row["close"]),
                "volume": safe_float(row["volume"]),
            }
            bars.append(bar)
    bars.sort(key=lambda x: x["ts"])
    return bars

def calculate_supertrend(bars, atr_length=10, multiplier=3.0):
    n = len(bars)
    tr = [0.0] * n
    atr = [None] * n
    for i in range(n):
        high, low = bars[i]["high"], bars[i]["low"]
        tr[i] = high - low if i == 0 else max(high - low, abs(high - bars[i - 1]["close"]), abs(low - bars[i - 1]["close"]))
    atr[atr_length - 1] = sum(tr[:atr_length]) / atr_length
    for i in range(atr_length, n):
        atr[i] = (atr[i - 1] * (atr_length - 1) + tr[i]) / atr_length
    upper, lower, direction = [None] * n, [None] * n, [None] * n
    start = atr_length - 1
    for i in range(start, n):
        midpoint = (bars[i]["high"] + bars[i]["low"]) / 2.0
        basic_upper = midpoint + multiplier * atr[i]
        basic_lower = midpoint - multiplier * atr[i]
        if i == start:
            upper[i], lower[i], direction[i] = basic_upper, basic_lower, 1
            continue
        prev_close = bars[i - 1]["close"]
        upper[i] = basic_upper if (basic_upper < upper[i - 1] or prev_close > upper[i - 1]) else upper[i - 1]
        lower[i] = basic_lower if (basic_lower > lower[i - 1] or prev_close < lower[i - 1]) else lower[i - 1]
        prev_dir, curr_close = direction[i - 1], bars[i]["close"]
        if prev_dir == -1 and curr_close > upper[i - 1]: direction[i] = 1
        elif prev_dir == 1 and curr_close < lower[i - 1]: direction[i] = -1
        else: direction[i] = prev_dir
    return atr, upper, lower, direction, start

def build_segments(bars, direction, start):
    segments = []
    current_direction = direction[start]
    entry_index = start + 1
    if entry_index >= len(bars): return segments
    entry_price = bars[entry_index]["open"]
    for i in range(start + 1, len(bars) - 1):
        signal = direction[i]
        if signal is None: continue
        if signal != current_direction:
            exit_index = i + 1
            exit_price = bars[exit_index]["open"]
            segments.append({
                "direction": current_direction, "entry_index": entry_index, "exit_index": exit_index,
                "entry_price": entry_price, "exit_price": exit_price,
            })
            current_direction = signal
            entry_index, entry_price = exit_index, exit_price
    segments.append({
        "direction": current_direction, "entry_index": entry_index, "exit_index": len(bars) - 1,
        "entry_price": entry_price, "exit_price": bars[-1]["close"],
    })
    return segments

def simulate_segments(bars, segments, cost_rate, directions=None):
    equity = CAPITAL
    curve = []
    trade_returns = []
    for index, segment in enumerate(segments):
        direction = directions[index] if directions is not None else segment["direction"]
        entry_index, exit_index = segment["entry_index"], segment["exit_index"]
        entry_price, exit_price = segment["entry_price"], segment["exit_price"]
        equity_before = equity
        for j in range(entry_index, exit_index):
            gross = direction * (bars[j]["close"] / entry_price - 1.0)
            curve.append(equity_before * (1.0 + gross))
        gross_return = direction * (exit_price / entry_price - 1.0)
        net_return = gross_return - cost_rate
        equity = equity_before * (1.0 + net_return)
        curve.append(equity)
        trade_returns.append(net_return * 100.0)
    wins = sum(1 for r in trade_returns if r > 0)
    pos_sum = sum(r for r in trade_returns if r > 0)
    neg_sum = abs(sum(r for r in trade_returns if r < 0))
    profit_factor = (pos_sum / neg_sum if neg_sum > 0 else float("inf") if pos_sum > 0 else 0.0)
    return {
        "final_equity": equity, "net_usd": equity - CAPITAL,
        "net_pct": (equity / CAPITAL - 1.0) * 100.0, "trades": len(trade_returns),
        "wins": wins, "win_rate": (wins / len(trade_returns) * 100.0 if trade_returns else 0.0),
        "maxdd": max_drawdown([CAPITAL] + curve), "profit_factor": profit_factor,
        "avg_trade_pct": (statistics.mean(trade_returns) if trade_returns else 0.0),
    }

def simulate_buy_hold(bars, segments, cost_rate):
    if not segments: return None
    entry_index, exit_index = segments[0]["entry_index"], segments[-1]["exit_index"]
    entry, exit_price = bars[entry_index]["open"], bars[exit_index]["close"]
    net = (exit_price / entry - 1.0) - cost_rate
    final_equity = CAPITAL * (1.0 + net)
    curve = [CAPITAL]
    for i in range(entry_index, exit_index):
        curve.append(CAPITAL * (1.0 + bars[i]["close"] / entry - 1.0))
    curve.append(final_equity)
    return {
        "final_equity": final_equity, "net_usd": final_equity - CAPITAL,
        "net_pct": net * 100.0, "trades": 1, "win_rate": 100.0 if net > 0 else 0.0,
        "maxdd": max_drawdown(curve),
    }

def simulate_random(bars, segments, cost_rate, seed):
    rng = random.Random(seed)
    random_dirs = [rng.choice([-1, 1]) for _ in segments]
    return simulate_segments(bars, segments, cost_rate, directions=random_dirs)

def analyze_csv(path):
    print("\n========== CSV SUMMARY ==========")
    print("FILE:", path)
    if not path.exists(): return
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    valid = []
    for r in rows:
        try: valid.append({"net": safe_float(r["net_pct"]), "buyhold": safe_float(r["buyhold_pct"]), "row": r})
        except: continue
    if not valid: return
    values = [x["net"] for x in valid]
    best, worst = max(valid, key=lambda x: x["net"]), min(valid, key=lambda x: x["net"])
    print("Total Grid Runs:", len(valid))
    print("Best net_pct:", pct(best["net"]))
    print("Worst net_pct:", pct(worst["net"]))
    print("Median net_pct:", pct(statistics.median(values)))
    print("Median buyhold_pct:", pct(statistics.median([x["buyhold"] for x in valid])))
    better = sum(1 for x in valid if x["net"] > x["buyhold"])
    print(f"Configs beating Buy & Hold: {better} of {len(valid)} ({better/len(valid)*100:.1f}%)")

def print_result(label, res):
    print(f"{label:<18} Net={usd(res['net_usd']):>10} | Return={pct(res['net_pct']):>11} | MaxDD={pct(res['maxdd']):>11} | WinRate={pct(res['win_rate']):>10} | Trades={res['trades']}")

def main():
    print("============================================")
    print("SUPERTREND OOS + BASELINE AUDIT (1000 BARS)")
    print("============================================")
    for p in CSV_FILES: analyze_csv(p)
    bars = load_ohlc(OHLC_FILE)
    atr, upper, lower, direction, start = calculate_supertrend(bars, ATR_LENGTH, ST_MULTIPLIER)
    segments = build_segments(bars, direction, start)
    print("\n========== TRADE SUMMARY ==========")
    print("Total Trades:", len(segments))
    for label, cost in COSTS.items():
        print("\n--------------------------------------------")
        print("SCENARIO:", label, f"(Round-trip: {cost*100:.2f}%)")
        st = simulate_segments(bars, segments, cost)
        bh = simulate_buy_hold(bars, segments, cost)
        rnd = simulate_random(bars, segments, cost, RANDOM_SEED)
        print_result("SUPERTREND", st)
        print_result("BUY & HOLD", bh)
        print_result("RANDOM BASELINE", rnd)
        print(f"SuperTrend Profit Factor: {st['profit_factor']:.2f}")

if __name__ == "__main__":
    main()
