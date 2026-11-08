"""Independent, research-only walk-forward TP/SL experiment."""
import json
import time
import urllib.request
import urllib.error
from itertools import product

from mi_core.pattern_lab import closed_ohlc, discover_signals
from mi_core.tpsl_path_eval import (
    _evaluate_signal_validated, _validate_bars, summarize_trades,
)

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
LIMIT = 1000
COST = 0.35
INITIAL_TRAIN = 400
TEST_SIZE = 100
MIN_TRAIN_RESOLVED = 12
TPS = (0.8, 1.2, 1.8)
SLS = (0.5, 0.8, 1.2)
HORIZONS = (3, 6)


def fetch_bars(symbol):
    url = f"{BASE}?symbol={symbol}&interval=1h&limit={LIMIT}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Market-Intelligence-WalkForward/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return closed_ohlc(raw, int(time.time() * 1000))


def pf_text(value):
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{value:.2f}"


def collect_trades(bars, entries, tp, sl, horizon, start, end):
    """Evaluate only signals in [start,end); never exit beyond end."""
    trades = []
    next_allowed = start

    for idx in sorted(entries):
        if idx < start or idx >= end or idx < next_allowed:
            continue

        trade = _evaluate_signal_validated(
            bars, idx, entries[idx], tp, sl, horizon,
            cost_pct=COST, ambiguous_policy="unresolved",
        )
        if trade["status"].startswith("UNAVAILABLE"):
            continue

        exit_idx = trade["exit_index"]
        if exit_idx is None or exit_idx >= end:
            continue

        trades.append(trade)
        # Ambiguous trades still occupy their full time window.
        next_allowed = exit_idx + 1

    return trades


def qualifies(stats):
    pf = stats["profit_factor"]
    return (
        stats["resolved"] >= MIN_TRAIN_RESOLVED
        and stats["avg_net_pct"] is not None
        and stats["avg_net_pct"] > 0
        and pf is not None
        and pf > 1.0
    )


def main():
    print("TP/SL WALK-FORWARD V2 | LARGER SAMPLE | RESEARCH ONLY")
    print("research_only=True | live_orders=False")
    print(
        f"interval=1h candles={LIMIT} initial_train={INITIAL_TRAIN} "
        f"test_fold={TEST_SIZE} cost={COST:.2f}%"
    )
    print("Training chooses parameters; each next fold is untouched OOS data.")
    print("Same-candle TP/SL ambiguity is unresolved, not guessed.")
    print("No data files written. No orders or signal changes.")

    for symbol in SYMBOLS:
        print(f"\n===== {symbol} =====")
        try:
            bars = fetch_bars(symbol)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print(f"FETCH_FAILED: {type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            print(f"DATA_FAILED: {type(exc).__name__}: {exc}")
            continue

        try:
            _validate_bars(bars)
        except (TypeError, ValueError) as exc:
            print(f"DATA_VALIDATION_FAILED: {type(exc).__name__}: {exc}")
            continue

        n = len(bars)
        if n < INITIAL_TRAIN + TEST_SIZE + 10:
            print(f"INSUFFICIENT_CLOSED_CANDLES: {n}")
            continue

        signals = discover_signals(bars, breakout_window=20)
        fold_starts = list(range(INITIAL_TRAIN, n, TEST_SIZE))
        aggregate = {name: [] for name in signals}
        selected_count = {name: 0 for name in signals}

        print(f"closed_candles={n} patterns={len(signals)} folds={len(fold_starts)}")
        print(f"first_ts_ms={bars[0]['ts']} last_ts_ms={bars[-1]['ts']}")

        for fold_no, start in enumerate(fold_starts, 1):
            end = min(start + TEST_SIZE, n)
            if end - start < 10:
                continue

            print(f"\n-- FOLD {fold_no}: train [0,{start}), test [{start},{end}) --")
            fold_selected = 0

            for name, entries in signals.items():
                candidates = []

                for tp, sl, horizon in product(TPS, SLS, HORIZONS):
                    train_trades = collect_trades(
                        bars, entries, tp, sl, horizon, 0, start
                    )
                    train_stats = summarize_trades(train_trades)

                    if qualifies(train_stats):
                        candidates.append((
                            train_stats["avg_net_pct"],
                            train_stats["profit_factor"],
                            train_stats["resolved"],
                            tp, sl, horizon,
                        ))

                if not candidates:
                    continue

                # Choose only from the training period.
                candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
                _, _, train_n, tp, sl, horizon = candidates[0]

                test_trades = collect_trades(
                    bars, entries, tp, sl, horizon, start, end
                )
                test_stats = summarize_trades(test_trades)
                aggregate[name].extend(test_trades)
                selected_count[name] += 1
                fold_selected += 1

                avg = test_stats["avg_net_pct"]
                avg_text = "n/a" if avg is None else f"{avg:+.3f}%"
                win = test_stats["win_rate_pct"]
                win_text = "n/a" if win is None else f"{win:.1f}%"

                print(
                    f"{name}: train_n={train_n}, chosen TP={tp:.1f}% "
                    f"SL={sl:.1f}% H={horizon}; "
                    f"OOS resolved={test_stats['resolved']} "
                    f"ambiguous={test_stats['ambiguous']} "
                    f"avg_net={avg_text} win={win_text} "
                    f"PF={pf_text(test_stats['profit_factor'])}"
                )

            if fold_selected == 0:
                print("NO_TRAIN_SELECTION: no pattern/config passed training gates.")

        print("\nOOS SUMMARY BY PATTERN (fold results combined, not a portfolio):")
        print("pattern | selected folds | resolved | ambiguous | avg net | win rate | PF")
        for name, trades in aggregate.items():
            stats = summarize_trades(trades)
            avg = stats["avg_net_pct"]
            avg_text = "n/a" if avg is None else f"{avg:+.3f}%"
            win = stats["win_rate_pct"]
            win_text = "n/a" if win is None else f"{win:.1f}%"
            print(
                f"{name} | {selected_count[name]} | {stats['resolved']} | "
                f"{stats['ambiguous']} | {avg_text} | {win_text} | "
                f"{pf_text(stats['profit_factor'])}"
            )

        print(
            "Caution: fold selections are adaptive and the same historical "
            "data is reused in later training windows. Treat the combined "
            "summary as diagnostic, not as a final untouched holdout."
        )

    print("\nWALK_FORWARD_FINISHED")
    print("research_only=True | live_orders=False")


if __name__ == "__main__":
    main()
