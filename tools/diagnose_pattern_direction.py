"""Independent candle-pattern direction inversion test. Research only."""
import json
import time
import urllib.request

from mi_core.pattern_lab import closed_ohlc, discover_signals
from mi_core.tpsl_path_eval import _evaluate_signal_validated, _validate_bars

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
LIMIT = 1000
TRAIN_END = 700
TEST_END = 900
TP = 1.2
SL = 0.8
HORIZON = 3
SELECTION_COST = 0.35
COSTS = (0.0, 0.05, 0.10, 0.20, 0.35)
MIN_TRAIN_TRADES = 12
PATTERNS = ("hammer", "bullish_engulfing", "bearish_engulfing")


def fetch_bars(symbol):
    url = f"{BASE}?symbol={symbol}&interval=1h&limit={LIMIT}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "MI-Pattern-Direction-Diagnostic/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return closed_ohlc(raw, int(time.time() * 1000))


def flip_entries(entries):
    """Keep the exact signal indices; reverse only their directions."""
    return {idx: -side for idx, side in entries.items()}


def collect(bars, entries, start, end):
    trades = []
    next_allowed = start

    for idx in sorted(entries):
        if idx < start or idx >= end or idx < next_allowed:
            continue

        trade = _evaluate_signal_validated(
            bars,
            idx,
            entries[idx],
            TP,
            SL,
            HORIZON,
            cost_pct=0.0,
            ambiguous_policy="unresolved",
        )

        if trade["status"].startswith("UNAVAILABLE"):
            continue

        exit_idx = trade.get("exit_index")
        if exit_idx is None or exit_idx >= end:
            continue

        trades.append(trade)
        next_allowed = exit_idx + 1

    return trades


def stats(trades, cost):
    resolved = [
        t for t in trades
        if isinstance(t.get("gross_pct"), (int, float))
    ]
    values = [float(t["gross_pct"]) - cost for t in resolved]
    wins = sum(x > 0 for x in values)
    profit = sum(x for x in values if x > 0)
    loss = -sum(x for x in values if x < 0)

    return {
        "n": len(values),
        "amb": sum(t.get("status") == "AMBIGUOUS" for t in trades),
        "avg": sum(values) / len(values) if values else None,
        "total": sum(values) if values else None,
        "win": 100 * wins / len(values) if values else None,
        "pf": profit / loss if loss else (
            float("inf") if profit > 0 else None
        ),
    }


def fmt(value, suffix="", digits=3):
    if value is None:
        return "NA"
    if isinstance(value, float) and value == float("inf"):
        return "INF"
    return f"{value:+.{digits}f}{suffix}"


def print_stats(label, s):
    print(
        f"{label}: n={s['n']} ambiguous={s['amb']} "
        f"avg={fmt(s['avg'], '%')} total={fmt(s['total'], '%')} "
        f"win={fmt(s['win'], '%', 1)} PF={fmt(s['pf'], '', 2)}"
    )


def eligible(s):
    return (
        s["n"] >= MIN_TRAIN_TRADES
        and s["avg"] is not None
        and s["avg"] > 0
        and s["pf"] is not None
        and s["pf"] > 1.0
    )


def main():
    print("PATTERN DIRECTION TEST | research_only=True | live_orders=False")
    print(
        f"1h TP={TP}% SL={SL}% horizon={HORIZON} "
        f"train=[0,{TRAIN_END}) test=[{TRAIN_END},{TEST_END})"
    )
    print(
        f"Selection cost={SELECTION_COST}% "
        f"minimum resolved train trades={MIN_TRAIN_TRADES}"
    )
    print("Only signal direction is reversed; signal indices stay fixed.")
    print("No market files written; no orders; no service control.")

    for symbol in SYMBOLS:
        print(f"\n=== {symbol} ===")
        try:
            bars = fetch_bars(symbol)
            _validate_bars(bars)
        except Exception as exc:
            print(f"DATA_FAILED: {type(exc).__name__}: {exc}")
            continue

        print(f"closed_candles={len(bars)}")
        if len(bars) < TEST_END + HORIZON + 2:
            print("INSUFFICIENT_DATA: skipped safely")
            continue

        signals = discover_signals(bars, breakout_window=20)

        for pattern in PATTERNS:
            original = signals[pattern]
            reversed_entries = flip_entries(original)
            variants = {
                "DIRECT": original,
                "REVERSED": reversed_entries,
            }

            print(f"\n-- {pattern} --")
            train_stats = {}
            for direction, entries in variants.items():
                trades = collect(bars, entries, 0, TRAIN_END)
                s = stats(trades, SELECTION_COST)
                train_stats[direction] = s
                print_stats(f"TRAIN {direction} cost={SELECTION_COST:.2f}%", s)

            candidates = [
                (s["avg"], direction, s)
                for direction, s in train_stats.items()
                if eligible(s)
            ]

            if candidates:
                _, chosen, chosen_s = max(candidates, key=lambda x: x[0])
                print(
                    f"TRAIN_ONLY_CHOICE={chosen} "
                    f"train_avg={fmt(chosen_s['avg'], '%')} "
                    f"train_n={chosen_s['n']}"
                )
            else:
                chosen = None
                print("TRAIN_ONLY_CHOICE=NONE (no direction passed the gate)")

            # OOS is reported for evaluation only and never selects the direction.
            test_trades = {}
            for direction, entries in variants.items():
                test_trades[direction] = collect(
                    bars, entries, TRAIN_END, TEST_END
                )
                print_stats(
                    f"OOS {direction} cost={SELECTION_COST:.2f}%",
                    stats(test_trades[direction], SELECTION_COST),
                )

            print("OOS COST SENSITIVITY (diagnostic only):")
            for direction in ("DIRECT", "REVERSED"):
                for cost in COSTS:
                    print_stats(
                        f"  {direction} cost={cost:.2f}%",
                        stats(test_trades[direction], cost),
                    )

            if chosen is not None:
                print(
                    "TRAIN-SELECTED OOS: "
                    f"{chosen} (selection was made using training data only)"
                )
                print_stats(
                    f"  SELECTED {chosen} OOS cost={SELECTION_COST:.2f}%",
                    stats(test_trades[chosen], SELECTION_COST),
                )
            else:
                print("TRAIN-SELECTED OOS: NONE; no direction is endorsed")

    print("\nDIRECTION_TEST_FINISHED")
    print("Small sample; research only, not a profitability guarantee.")


if __name__ == "__main__":
    main()
