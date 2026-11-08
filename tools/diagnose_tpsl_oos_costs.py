"""Independent OOS gross-vs-cost diagnostic; research only."""
import json
import time
import urllib.request
import urllib.error

from mi_core.pattern_lab import closed_ohlc, discover_signals
from mi_core.tpsl_path_eval import (
    _evaluate_signal_validated,
    _validate_bars,
)

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
LIMIT = 1000
TRAIN_SIZE = 700
TEST_SIZE = 200
TP = 1.2
SL = 0.8
HORIZON = 3
COSTS = (0.0, 0.05, 0.10, 0.20, 0.35)


def fetch_bars(symbol):
    url = f"{BASE}?symbol={symbol}&interval=1h&limit={LIMIT}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Market-Intelligence-Cost-Diagnostic/1.0"}
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return closed_ohlc(raw, int(time.time() * 1000))


def collect_gross_trades(bars, entries, start, end):
    """Freeze trade selection and outcomes before applying cost scenarios."""
    trades = []
    next_allowed = start

    for idx in sorted(entries):
        if idx < start or idx >= end or idx < next_allowed:
            continue

        trade = _evaluate_signal_validated(
            bars, idx, entries[idx], TP, SL, HORIZON,
            cost_pct=0.0, ambiguous_policy="unresolved",
        )

        if trade["status"].startswith("UNAVAILABLE"):
            continue

        exit_idx = trade["exit_index"]
        if exit_idx is None or exit_idx >= end:
            continue

        trades.append(trade)
        next_allowed = exit_idx + 1

    return trades


def metrics(trades, cost):
    resolved = [
        t for t in trades
        if isinstance(t.get("gross_pct"), (int, float))
    ]
    values = [float(t["gross_pct"]) - cost for t in resolved]
    wins = sum(v > 0 for v in values)
    profit = sum(v for v in values if v > 0)
    loss = -sum(v for v in values if v < 0)

    avg = sum(values) / len(values) if values else None
    total = sum(values) if values else None
    win_rate = 100 * wins / len(values) if values else None
    pf = (
        profit / loss if loss > 0
        else (float("inf") if profit > 0 else None)
    )

    return {
        "resolved": len(values),
        "ambiguous": sum(t.get("status") == "AMBIGUOUS" for t in trades),
        "avg": avg,
        "total": total,
        "win_rate": win_rate,
        "pf": pf,
    }


def fmt(value, suffix="", digits=3):
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{value:+.{digits}f}{suffix}"


def main():
    print("OOS GROSS VS COST | research_only=True | live_orders=False")
    print(
        f"interval=1h candles_limit={LIMIT} train={TRAIN_SIZE} "
        f"test=[{TRAIN_SIZE},{TRAIN_SIZE + TEST_SIZE}) "
        f"TP={TP}% SL={SL}% horizon={HORIZON}"
    )
    print("Same selected trades/outcomes across all cost scenarios.")
    print("No market files written; no orders; no service control.")

    for symbol in SYMBOLS:
        print(f"\n=== {symbol} ===")
        try:
            bars = fetch_bars(symbol)
            _validate_bars(bars)
        except Exception as exc:
            print(f"DATA_FAILED: {type(exc).__name__}: {exc}")
            continue

        n = len(bars)
        print(f"closed_candles={n}")
        if n < TRAIN_SIZE + TEST_SIZE + HORIZON + 2:
            print("INSUFFICIENT_DATA: skipped safely")
            continue

        signals = discover_signals(bars, breakout_window=20)

        for name, entries in signals.items():
            trades = collect_gross_trades(
                bars, entries, TRAIN_SIZE, TRAIN_SIZE + TEST_SIZE
            )
            if not trades:
                print(f"\n{name}: no accepted OOS trades")
                continue

            base = metrics(trades, 0.0)
            print(
                f"\n{name}: OOS resolved={base['resolved']} "
                f"ambiguous={base['ambiguous']} "
                f"gross_avg={fmt(base['avg'], '%')} "
                f"gross_sum={fmt(base['total'], '%')}"
            )

            for cost in COSTS:
                m = metrics(trades, cost)
                print(
                    f"  cost={cost:.2f}% "
                    f"avg_net={fmt(m['avg'], '%')} "
                    f"sum_net={fmt(m['total'], '%')} "
                    f"win={fmt(m['win_rate'], '%', 1)} "
                    f"PF={fmt(m['pf'], '', 2)}"
                )

    print("\nCOST_DIAGNOSTIC_FINISHED")
    print("Small historical sample; not evidence of future profitability.")


if __name__ == "__main__":
    main()
