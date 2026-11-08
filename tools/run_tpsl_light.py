"""Lightweight, independent, research-only TP/SL diagnostic."""
import json
import time
import urllib.request
import urllib.error

from mi_core.pattern_lab import closed_ohlc, discover_signals
from mi_core.tpsl_path_eval import (
    _evaluate_signal_validated,
    _validate_bars,
    summarize_trades,
)

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
LIMIT = 1000
TRAIN_SIZE = 700
TEST_SIZE = 200
TP = 1.2
SL = 0.8
HORIZON = 3
COST = 0.35


def fetch_bars(symbol):
    url = f"{BASE}?symbol={symbol}&interval=1h&limit={LIMIT}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Market-Intelligence-Light/1.0"}
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return closed_ohlc(raw, int(time.time() * 1000))


def collect(bars, entries, start, end):
    trades = []
    next_allowed = start

    for idx in sorted(entries):
        if idx < start or idx >= end or idx < next_allowed:
            continue
        trade = _evaluate_signal_validated(
            bars, idx, entries[idx], TP, SL, HORIZON,
            cost_pct=COST, ambiguous_policy="unresolved",
        )
        if trade["status"].startswith("UNAVAILABLE"):
            continue
        exit_idx = trade["exit_index"]
        if exit_idx is None or exit_idx >= end:
            continue
        trades.append(trade)
        next_allowed = exit_idx + 1

    return trades


def show_stats(label, trades):
    stats = summarize_trades(trades)
    avg = stats["avg_net_pct"]
    win = stats["win_rate_pct"]
    pf = stats["profit_factor"]
    print(
        f"{label}: resolved={stats['resolved']} "
        f"ambiguous={stats['ambiguous']} "
        f"avg_net={'n/a' if avg is None else f'{avg:+.3f}%'} "
        f"win={'n/a' if win is None else f'{win:.1f}%'} "
        f"PF={'n/a' if pf is None else f'{pf:.2f}'}"
    )


def main():
    print("LIGHT TP/SL DIAGNOSTIC | research_only=True | live_orders=False")
    print(
        f"interval=1h limit={LIMIT} train={TRAIN_SIZE} test={TEST_SIZE} "
        f"TP={TP}% SL={SL}% horizon={HORIZON} cost={COST}%"
    )
    print("No files written; no orders; no service control.")

    for symbol in SYMBOLS:
        print(f"\n=== {symbol} ===")
        try:
            bars = fetch_bars(symbol)
            _validate_bars(bars)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print(f"DATA_FAILED: {type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            print(f"DATA_FAILED: {type(exc).__name__}: {exc}")
            continue

        n = len(bars)
        print(f"closed_candles={n}")
        if n < TRAIN_SIZE + TEST_SIZE + HORIZON + 2:
            print("INSUFFICIENT_DATA: skipped safely")
            continue

        signals = discover_signals(bars, breakout_window=20)
        print(f"patterns={len(signals)}")

        for name, entries in signals.items():
            train = collect(bars, entries, 0, TRAIN_SIZE)
            train_stats = summarize_trades(train)
            # Keep this a diagnostic, not a strategy-selection system.
            test = collect(bars, entries, TRAIN_SIZE, TRAIN_SIZE + TEST_SIZE)
            print(
                f"\n{name}: train resolved={train_stats['resolved']} "
                f"train ambiguous={train_stats['ambiguous']}"
            )
            show_stats("OOS", test)

    print("\nLIGHT_DIAGNOSTIC_FINISHED")
    print("Research only. Results do not establish future profitability.")


if __name__ == "__main__":
    main()
