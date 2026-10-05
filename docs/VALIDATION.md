# Validation Protocol

A strategy is not deployable because one backtest is profitable.

1. Validate timestamps, prices and symbols.
2. Keep raw observations append-only.
3. Build features only from information available at decision time.
4. Model fees, slippage and execution latency.
5. Use chronological train/test separation.
6. Run rolling walk-forward out-of-sample evaluation.
7. Run Monte Carlo on trade returns.
8. Apply profitability and drawdown gates.
9. Compare OOS performance with training performance.
10. Record every shadow signal and eventual outcome.
11. Segment results by regime, symbol and signal reason.
12. Only stable OOS evidence can qualify a strategy for later live-execution research.

This repository intentionally contains no live order placement or exchange credentials.
