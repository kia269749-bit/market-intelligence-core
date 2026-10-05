# Chronological Train/Test and Walk-Forward OOS

This module is a deterministic research primitive for avoiding lookahead during historical validation.

## Guarantees
- Input timestamps must be strictly increasing.
- Duplicate timestamps are rejected.
- Every fold's training observations end before its test observations begin.
- Rolling windows keep a fixed training size.
- Anchored windows keep the original training start and expand it forward.
- The test window never overlaps the training window.
- No network, credentials, exchange access, or order execution is used.

## API
chronological_split(items, timestamps, train_size, test_size) creates one train/test split.
walk_forward(items, timestamps, train_size, test_size, step, anchored=False) creates rolling folds. With anchored=True, the training window expands from the beginning.
step defaults to test_size.

## Cost policy
Walk-forward itself does not invent execution costs. Downstream backtests should use the existing ExecutionCostConfig and keep its assumptions fixed across OOS folds. Alternative costs should be modeled as explicit stress scenarios, not silently changed per fold.

This is research/paper infrastructure only. It does not produce trading orders or imply profitability.
