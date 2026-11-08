"""Research-only OHLC TP/SL walk-forward experiment. No orders, no data files."""
import json
import time
import urllib.request
import urllib.error
from itertools import product

from mi_core.pattern_lab import closed_ohlc, discover_signals
from mi_core.tpsl_path_eval import evaluate_signal, summarize_trades

BASE = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
LIMIT = 500
COST = 0.35
TRAIN_FRACTION = 0.60
MIN_TRAIN_TRADES = 8
TPS = (0.8, 1.2, 1.8)
SLS = (0.5, 0.8, 1.2)
HORIZONS = (3, 6)


def fetch_closed(symbol):
    url = f"{BASE}?symbol={symbol}&interval=1h&limit={LIMIT}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Market-Intelligence-TP-SL-Lab/1.0"}
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


def evaluate_pattern(bars, entries, tp, sl, horizon, split):
    train, test = [], []
    next_allowed = 0

    for idx in sorted(entries):
        if idx < next_allowed:
            continue

        trade = evaluate_signal(
            bars, idx, entries[idx], tp, sl, horizon,
            cost_pct=COST,
            ambiguous_policy="unresolved",
        )
        if trade["status"].startswith("UNAVAILABLE"):
            continue

        exit_idx = trade["exit_index"]
        if idx < split:
            # Never let a training trade use candles from the test period.
            if exit_idx >= split:
                continue
            train.append(trade)
        else:
            test.append(trade)

        # An ambiguous trade still occupies its time window.
        next_allowed = exit_idx + 1

    return summarize_trades(train), summarize_trades(test)


def eligible(stats):
    pf = stats["profit_factor"]
    return (
        stats["resolved"] >= MIN_TRAIN_TRADES
        and stats["avg_net_pct"] is not None
        and stats["avg_net_pct"] > 0
        and pf is not None
        and pf > 1.0
    )


def main():
    print("REAL OHLC TP/SL LAB | RESEARCH ONLY")
    print("research_only=True | live_orders=False")
    print(f"interval=1h | candles_requested={LIMIT} per asset")
    print(f"round_trip_cost={COST:.2f}% | train_fraction={TRAIN_FRACTION:.0%}")
    print("Ambiguous same-candle TP/SL trades are not assigned PnL.")
    print("No orders, no project signal changes, no data files written.")

    for symbol in SYMBOLS:
        print(f"\n===== {symbol} =====")
        try:
            bars = fetch_closed(symbol)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            print(f"FETCH_FAILED: {type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            print(f"DATA_FAILED: {type(exc).__name__}: {exc}")
            continue

        if len(bars) < 150:
            print(f"INSUFFICIENT_CLOSED_CANDLES: {len(bars)}")
            continue

        split = int(len(bars) * TRAIN_FRACTION)
        patterns = discover_signals(bars, breakout_window=20)
        print(f"closed_candles={len(bars)} split_index={split}")
        print(f"first_ts_ms={bars[0]['ts']} last_ts_ms={bars[-1]['ts']}")
        print(f"patterns={len(patterns)} configurations_per_pattern="
              f"{len(TPS) * len(SLS) * len(HORIZONS)}")

        results = []
        for name, entries in patterns.items():
            for tp, sl, horizon in product(TPS, SLS, HORIZONS):
                tr, te = evaluate_pattern(
                    bars, entries, tp, sl, horizon, split
                )
                results.append({
                    "pattern": name, "tp": tp, "sl": sl,
                    "horizon": horizon, "train": tr, "test": te,
                    "selected": eligible(tr),
                })

        selected = [r for r in results if r["selected"]]
        print(f"train_selected_configs={len(selected)} / {len(results)}")
        print("Only training data selects configurations; test is reported afterward.")

        if not selected:
            print("NO_TRAIN_CONFIG_PASSED: no configuration met the pre-set "
                  "training requirements. No winner will be invented.")
            continue

        # Test outcomes are displayed only for configurations selected on train.
        # This is diagnostic, not proof of future profitability.
        selected.sort(
            key=lambda r: (
                r["test"]["avg_net_pct"] is not None,
                r["test"]["avg_net_pct"] if r["test"]["avg_net_pct"] is not None else -999,
            ),
            reverse=True,
        )
        print("pattern | TP% | SL% | horizon | train n/avg/PF | "
              "test n/avg/PF | test wins% | ambiguous test")
        for r in selected[:8]:
            tr, te = r["train"], r["test"]
            win = te["win_rate_pct"]
            win_text = "n/a" if win is None else f"{win:.1f}"
            avg_tr = "n/a" if tr["avg_net_pct"] is None else f"{tr['avg_net_pct']:+.3f}"
            avg_te = "n/a" if te["avg_net_pct"] is None else f"{te['avg_net_pct']:+.3f}"
            print(
                f"{r['pattern']} | {r['tp']:.1f} | {r['sl']:.1f} | "
                f"{r['horizon']} | {tr['resolved']}/{avg_tr}/{pf_text(tr['profit_factor'])} | "
                f"{te['resolved']}/{avg_te}/{pf_text(te['profit_factor'])} | "
                f"{win_text} | {te['ambiguous']}"
            )

        print("Interpretation: net averages are percentage points after stated costs.")
        print("These are exploratory results across many configurations; "
              "they do not establish a reliable edge.")

    print("\nTPSL_REAL_OHLC_LAB_FINISHED")
    print("research_only=True | live_orders=False")


if __name__ == "__main__":
    main()
