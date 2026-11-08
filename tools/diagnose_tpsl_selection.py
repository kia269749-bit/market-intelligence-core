"""Research-only diagnostics for TP/SL walk-forward selection gates."""
from itertools import product

from run_tpsl_walkforward_v2 import (
    SYMBOLS, INITIAL_TRAIN, TEST_SIZE, MIN_TRAIN_RESOLVED,
    TPS, SLS, HORIZONS, fetch_bars, collect_trades, qualifies,
)
from mi_core.pattern_lab import discover_signals
from mi_core.tpsl_path_eval import summarize_trades


def main():
    print("TP/SL SELECTION GATE DIAGNOSTICS")
    print("TRAINING DATA ONLY | RESEARCH ONLY | NO ORDERS")
    print("Gate counts may overlap; top candidates are NOT OOS evidence.")

    for symbol in SYMBOLS:
        print(f"\n===== {symbol} =====")
        try:
            bars = fetch_bars(symbol)
        except Exception as exc:
            print(f"FETCH_FAILED: {type(exc).__name__}: {exc}")
            continue

        signals = discover_signals(bars, breakout_window=20)
        n = len(bars)
        print(f"closed_candles={n} patterns={len(signals)}")

        for fold_no, start in enumerate(
            range(INITIAL_TRAIN, n, TEST_SIZE), 1
        ):
            end = min(start + TEST_SIZE, n)
            if end - start < 10:
                continue

            counts = {
                "total": 0, "low_resolved": 0, "avg_missing": 0,
                "avg_nonpositive": 0, "pf_missing": 0,
                "pf_le_1": 0, "passed": 0,
            }
            candidates = []

            for name, entries in signals.items():
                for tp, sl, horizon in product(TPS, SLS, HORIZONS):
                    trades = collect_trades(
                        bars, entries, tp, sl, horizon, 0, start
                    )
                    stats = summarize_trades(trades)
                    counts["total"] += 1

                    resolved = stats["resolved"]
                    avg = stats["avg_net_pct"]
                    pf = stats["profit_factor"]

                    if resolved < MIN_TRAIN_RESOLVED:
                        counts["low_resolved"] += 1
                    if avg is None:
                        counts["avg_missing"] += 1
                    elif avg <= 0:
                        counts["avg_nonpositive"] += 1
                    if pf is None:
                        counts["pf_missing"] += 1
                    elif pf <= 1:
                        counts["pf_le_1"] += 1

                    if qualifies(stats):
                        counts["passed"] += 1

                    if resolved >= MIN_TRAIN_RESOLVED and avg is not None:
                        candidates.append(
                            (avg, pf, resolved, name, tp, sl, horizon)
                        )

            print(
                f"\nFOLD {fold_no} train=[0,{start}) "
                f"test=[{start},{end})"
            )
            print("configs={total} | low_resolved={low_resolved} | "
                  "avg_missing={avg_missing} | avg_nonpositive={avg_nonpositive} | "
                  "pf_missing={pf_missing} | pf_le_1={pf_le_1} | "
                  "passed={passed}".format(**counts))

            candidates.sort(
                key=lambda x: (
                    x[0],
                    float("-inf") if x[1] is None else x[1],
                    x[2],
                ),
                reverse=True,
            )
            print("Top 3 training candidates with enough resolved trades:")
            if not candidates:
                print("  NONE")
            for avg, pf, resolved, name, tp, sl, horizon in candidates[:3]:
                pf_text = "n/a" if pf is None else (
                    "inf" if pf == float("inf") else f"{pf:.2f}"
                )
                passed = avg > 0 and pf is not None and pf > 1
                print(
                    f"  {name}: n={resolved} avg_net={avg:+.3f}% "
                    f"PF={pf_text} TP={tp:.1f}% SL={sl:.1f}% "
                    f"H={horizon} passes_profit_gates={passed}"
                )

    print("\nDIAGNOSTICS_FINISHED")
    print("Training rankings are not proof of future profitability.")


if __name__ == "__main__":
    main()
