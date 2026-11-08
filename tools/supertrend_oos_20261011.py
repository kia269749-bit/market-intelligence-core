import json, math, csv
from pathlib import Path

DATA = Path("data/real_oos_audit/multitimeframe_20261011")
OUT = Path("data/real_oos_audit/supertrend_oos_20261011.csv")
COSTS = (0.0010, 0.0035)
PERIODS = (7, 10, 14)
MULTS = (2.0, 2.5, 3.0, 4.0)

def load(path):
    rows = []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            x = json.loads(line)
            r = {k: float(x[k]) for k in ("open", "high", "low", "close")}
            r["ts"] = int(x["ts"])
            if (all(math.isfinite(r[k]) and r[k] > 0
                    for k in ("open", "high", "low", "close"))
                and r["high"] >= max(r["open"], r["close"], r["low"])
                and r["low"] <= min(r["open"], r["close"])):
                rows.append(r)
    rows.sort(key=lambda x: x["ts"])
    result = []
    for r in rows:
        if not result or r["ts"] != result[-1]["ts"]:
            result.append(r)
    return result

def calc(rows, period, mult):
    n = len(rows)
    tr = []
    for i, r in enumerate(rows):
        if i == 0:
            tr.append(r["high"] - r["low"])
        else:
            prev = rows[i-1]["close"]
            tr.append(max(r["high"]-r["low"],
                          abs(r["high"]-prev), abs(r["low"]-prev)))
    atr = [None]*n
    if n < period:
        return [None]*n
    atr[period-1] = sum(tr[:period])/period
    for i in range(period, n):
        atr[i] = (atr[i-1]*(period-1)+tr[i])/period

    direction = [None]*n
    upper, lower = [None]*n, [None]*n
    for i, r in enumerate(rows):
        if atr[i] is None:
            continue
        mid = (r["high"]+r["low"])/2
        bu, bl = mid+mult*atr[i], mid-mult*atr[i]
        if i == period-1:
            upper[i], lower[i] = bu, bl
            direction[i] = 1 if r["close"] >= mid else -1
            continue
        pu, pl = upper[i-1], lower[i-1]
        pc = rows[i-1]["close"]
        upper[i] = bu if bu < pu or pc > pu else pu
        lower[i] = bl if bl > pl or pc < pl else pl
        pd = direction[i-1]
        if pd == -1:
            direction[i] = 1 if r["close"] > upper[i] else -1
        else:
            direction[i] = -1 if r["close"] < lower[i] else 1
    return direction

def run(rows, direction, start, end, cost, interval):
    # Start/end are chronological split indices.
    # Positions are closed at split end; never cross a data gap.
    trades, pos, entry = [], False, None
    for i in range(max(start+1, 1), end):
        prev, cur = rows[i-1], rows[i]
        gap = cur["ts"]-prev["ts"] > interval*1.5
        if gap and pos:
            ret = cur["open"]/entry-1-cost
            trades.append(ret)
            pos, entry = False, None
        d = direction[i-1]
        if d is None:
            continue
        if not pos and d == 1:
            pos, entry = True, cur["open"]
        elif pos and d == -1:
            trades.append(cur["open"]/entry-1-cost)
            pos, entry = False, None
    if pos and entry is not None and end > start:
        trades.append(rows[end-1]["close"]/entry-1-cost)
    equity, peak, dd = 1.0, 1.0, 0.0
    for ret in trades:
        equity *= max(0.000001, 1+ret)
        peak = max(peak, equity)
        dd = max(dd, (peak-equity)/peak)
    wins = [x for x in trades if x > 0]
    losses = [-x for x in trades if x < 0]
    pf = sum(wins)/sum(losses) if sum(losses) else (999 if wins else 0)
    bh = rows[end-1]["close"]/rows[start]["open"]-1 if end-start > 1 else 0
    return [len(trades), round((equity-1)*100,3),
            round(sum(trades)/len(trades)*100,3) if trades else 0,
            round(len(wins)/len(trades)*100,1) if trades else 0,
            round(pf,3), round(dd*100,2), round(bh*100,3)]

def main():
    files = [
        (sym, tf, DATA/f"{sym}_{tf}.jsonl", ms)
        for sym in ("BTCUSDT","ETHUSDT")
        for tf, ms in (("5m",300000),("15m",900000),
                       ("1h",3600000),("4h",14400000))
    ]
    header = ["symbol","tf","part","atr","mult","cost","trades",
              "net_pct","avg_trade_pct","win_pct","pf","maxdd_pct","buyhold_pct"]
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for sym, tf, path, ms in files:
            if not path.exists():
                continue
            rows = load(path)
            n = len(rows)
            if n < 100:
                continue
            # Do not join across gaps: skip this file if timestamps are irregular.
            if any(rows[i]["ts"]-rows[i-1]["ts"] > ms*1.5 for i in range(1,n)):
                print("SKIP_GAPS", sym, tf)
                continue
            a, b = int(n*.60), int(n*.80)
            for p in PERIODS:
                for m in MULTS:
                    d = calc(rows,p,m)
                    for part, lo, hi in (("TRAIN",0,a),("VALID",a,b),("TEST",b,n)):
                        for cost in COSTS:
                            result = run(rows,d,lo,hi,cost,ms)
                            w.writerow([sym,tf,part,p,m,cost]+result)
    print("Saved:", OUT)
    print("Columns: trades, net return, average trade, win rate, profit factor, drawdown, buy-and-hold")
    print("Reminder: estimated costs only; slippage and funding are not modeled.")

if __name__ == "__main__":
    main()
