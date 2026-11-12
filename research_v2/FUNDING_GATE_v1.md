# Funding-feature test gate v1 (LOCKED 2026-11-12, amended before any economic run)
Hypothesis count for Holm correction: 2 (v4 base model, v4 + Funding features).
Data: same Hyperliquid perpetual candles/funding and Walk-Forward framework as v4 (CI run 323); OI excluded (no history).
Cost: one Taker round-trip rate of 0.12% from mi_core/cost_policy.py.
PASS requires ALL of:
1. At least 300 resolved OOS trades in total, from at least 3 assets.
2. Net profit > 0 after the 0.12% Taker round-trip cost.
3. Beats v4-without-Funding and Buy & Hold, Holm-adjusted p <= 0.05 with 2 hypotheses.
4. Max drawdown from daily equity curve <= 20%.
5. Result judged only on the first complete run; technical-bug fixes allowed but every run is logged, no later run replaces it.
6. Any failure: research project closed; only the signal-bot forward test (100 trades) remains.
No threshold, cost, asset list or metric change after seeing results. No demo/testnet, no Kronos until PASS.
