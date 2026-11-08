"""Independent pattern/regime diagnostic. Research only, no orders."""
import json
import time
import urllib.request

from mi_core.pattern_lab import closed_ohlc, discover_signals
from mi_core.tpsl_path_eval import (
    _evaluate_signal_validated,
    _validate_bars,
)

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

FILTERS = (
    "none",
    "above_sma20",
    "below_sma20",
    "bull_trend",
    "bear_trend",
)


def fetch_bars(symbol):
    url = f"{BASE}?symbol={symbol}&interval=1h&limit={LIMIT}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Market-Intelligence-Regime-Diagnostic/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return closed_ohlc(raw, int(time.time() * 1000))


def regime_flags(bars):
    """Use only candles at or before each signal index."""
    closes = [float(b["close"]) for b in bars]
    flags = {}

    for i in range(len(bars)):
        if i < 49:
            flags[i] = {
                "above_sma20": False,
                "below_sma20": False,
                "bull_trend": False,
                "bear_trend": False,
            }
            continue

        sma20 = sum(closes[i - 19:i + 1]) / 20
        sma50 = sum(closes[i - 49:i + 1]) / 50
        close = closes[i]

        flags[i] = {
            "above_sma20": close > sma20,
            "below_sma20": close < sma20,
            "bull_trend": close > sma20 and sma20 > sma50,
            "bear_trend": close < sma20 and sma20 < sma50,
        }

    return flags


def passes_filter(filter_name, idx, flags):
    if filter_name == "none":
        return True
    return flags[idx][filter_name]


def collect(bars, entries, flags, filter_name, start, end):
    trades = []
    next_allowed = start

    for idx in sorted(entries):
        if idx < start or idx >= end or idx < next_allowed:
            continue
        if not passes_filter(filter_name, idx, flags):
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


def fmt(x, suffix="", digits=3):
    if x is None:
        return "n/a"
    if x == float("inf"):
        return "inf"
    return f"{x:+.{digits}f}{suffix}"


def print_stats(label, s):
    print(
        f"{label}: n={s['n']} ambiguous={s['amb']} "
        f"avg={fmt(s['avg'], '%')} total={fmt(s['total'], '%')} "
        f"win={fmt(s['win'], '%', 1)} PF={fmt(s['pf'], '', 2)}"
    )


def main():
    print("PATTERN REGIME TEST | research_only=True | live_orders=False")
    print(
        f"1h TP={TP}% SL={SL}% horizon={HORIZON} "
        f"train=[0,{TRAIN_END}) test=[{TRAIN_END},{TEST_END})"
    )
    print(
        f"Training selection cost={SELECTION_COST}% "
        f"minimum resolved training trades={MIN_TRAIN_TRADES}"
    )
    print("Regimes use only completed candles up to signal time.")
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
        flags = regime_flags(bars)

        for pattern in PATTERNS:
            entries = signals[pattern]
            print(f"\n-- {pattern} --")
            train_by_filter = {}

            for filter_name in FILTERS:
                train = collect(
                    bars, entries, flags, filter_name, 0, TRAIN_END
                )
                train_stats = stats(train, SELECTION_COST)
                train_by_filter[filter_name] = (train, train_stats)
                print_stats(f"TRAIN {filter_name}", train_stats)

            eligible = []
            for filter_name, (_, s) in train_by_filter.items():
                if (
                    s["n"] >= MIN_TRAIN_TRADES
                    and s["avg"] is not None and s["avg"] > 0
                    and s["pf"] is not None and s["pf"] > 1.0
                ):
                    eligible.append((s["avg"], filter_name, s))

            if eligible:
                _, chosen, chosen_stats = max(eligible, key=lambda x: x[0])
                print(
                    f"TRAIN_ONLY_CHOICE={chosen} "
                    f"train_avg={fmt(chosen_stats['avg'], '%')} "
                    f"train_n={chosen_stats['n']}"
                )
            else:
                chosen = None
                print("TRAIN_ONLY_CHOICE=NONE (no filter passed the gate)")

            # OOS rows are for evaluation only, never used to choose a filter.
            for filter_name in FILTERS:
                test = collect(
                    bars, entries, flags, filter_name, TRAIN_END, TEST_END
                )
                print_stats(f"OOS {filter_name} cost=0.35%", stats(test, 0.35))

                if filter_name == "none":
                    print("  Baseline cost sensitivity:")
                    for cost in COSTS:
                        print_stats(
                            f"    baseline cost={cost:.2f}%",
                            stats(test, cost),
                        )

            if chosen is not None:
                chosen_test = collect(
                    bars, entries, flags, chosen, TRAIN_END, TEST_END
                )
                print("  TRAIN-CHOSEN FILTER OOS COST SENSITIVITY:")
                for cost in COSTS:
                    print_stats(
                        f"    chosen={chosen} cost={cost:.2f}%",
                        stats(chosen_test, cost),
                    )

    print("\nREGIME_DIAGNOSTIC_FINISHED")
    print("Small sample; research only, not a profitability guarantee.")


if __name__ == "__main__":
    main()
