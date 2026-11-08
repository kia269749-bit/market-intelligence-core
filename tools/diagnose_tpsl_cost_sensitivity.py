"""Training-only cost sensitivity; not a strategy selection tool."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import run_tpsl_walkforward_v2 as wf
from mi_core.pattern_lab import discover_signals
from mi_core.tpsl_path_eval import summarize_trades


def main():
    costs = (0.00, 0.05, 0.10, 0.20, 0.35)
    print("TP/SL COST SENSITIVITY")
    print("TRAINING ONLY | RESEARCH ONLY | NO ORDERS")
    print("Zero cost is diagnostic only, not a realistic trading assumption.")

    for symbol in wf.SYMBOLS:
        try:
            bars = wf.fetch_bars(symbol)
        except Exception as exc:
            print(f"\n{symbol}: FETCH_FAILED {type(exc).__name__}: {exc}")
            continue

        signals = discover_signals(bars, breakout_window=20)
        n = len(bars)
        print(f"\n===== {symbol}: closed_candles={n} =====")

        for start in range(wf.INITIAL_TRAIN, n, wf.TEST_SIZE):
            if min(start + wf.TEST_SIZE, n) - start < 10:
                continue

            print(f"\nTRAIN [0,{start})")
            print("cost | configs | enough_samples | positive_avg | PF>1 | pass_all | best_avg")

            for cost in costs:
                wf.COST = cost
                total = enough = positive = pf_gt1 = passed = 0
                best = None

                for name, entries in signals.items():
                    for tp in wf.TPS:
                        for sl in wf.SLS:
                            for horizon in wf.HORIZONS:
                                trades = wf.collect_trades(
                                    bars, entries, tp, sl, horizon, 0, start
                                )
                                st = summarize_trades(trades)
                                total += 1
                                avg = st["avg_net_pct"]
                                pf = st["profit_factor"]

                                if st["resolved"] < wf.MIN_TRAIN_RESOLVED:
                                    continue
                                enough += 1

                                if avg is not None and avg > 0:
                                    positive += 1
                                if pf is not None and pf > 1:
                                    pf_gt1 += 1

                                if wf.qualifies(st):
                                    passed += 1

                                if avg is not None and (
                                    best is None or avg > best[0]
                                ):
                                    best = (
                                        avg, name, tp, sl, horizon,
                                        st["resolved"], pf
                                    )

                if best is None:
                    best_text = "none"
                else:
                    avg, name, tp, sl, horizon, resolved, pf = best
                    pf_text = "n/a" if pf is None else (
                        "inf" if pf == float("inf") else f"{pf:.2f}"
                    )
                    best_text = (
                        f"{name}:avg={avg:+.3f}% PF={pf_text} "
                        f"n={resolved} TP={tp:.1f} SL={sl:.1f} H={horizon}"
                    )

                print(
                    f"{cost:.2f}% | {total} | {enough} | {positive} | "
                    f"{pf_gt1} | {passed} | {best_text}"
                )

    wf.COST = 0.35
    print("\nCOST_SENSITIVITY_FINISHED")
    print("Results are training diagnostics, not OOS proof.")


if __name__ == "__main__":
    main()
