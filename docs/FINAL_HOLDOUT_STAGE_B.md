# Stage B: locked chronological holdout

The calendar lock spans 2020-10-05 through 2026-10-12 inclusive: 2,199 calendar days.
Development is 2020-10-05 through 2025-07-29 inclusive (1,759 days). The untouched final holdout is 2025-07-30 through 2026-10-12 inclusive (440 days). The final segment is about 1.2 years and represents only one market regime; this materially limits confidence in any final result.

The lock file is `config/final_holdout_lock.json`. Its SHA-256 is recorded in the Stage B PR description/commit report and must be verified against the committed bytes. The loader accepts one caller-supplied partition file per call. Development mode fails closed on any out-of-range row, including a row on/after the holdout boundary; final holdout access is a separate explicit `step="final-step"` call and must use a distinct file. A static regression test scans production Python modules to ensure the final dataset path is not embedded and no development/strategy module calls the locked-holdout loader or explicit final-step mode. The poison-row test confirms a contaminated development partition is rejected.

The 30-asset universe is the currently listed Binance USDT spot universe from the coverage audit. It has survivorship bias: delisted/failed assets are absent. The 22-asset >=5-year subset is a robustness comparison, not a cure for survivorship bias. Daily OHLC coverage does not provide historical spread or slippage.

Annual and monthly counts from the completed raw coverage artifact are recorded in [`ASSET_COVERAGE_COUNTS.md`](ASSET_COVERAGE_COUNTS.md). The exact 30-symbol universe and audit-marked 22-symbol five-year subset are recorded in [`config/asset_universe_sets.json`](../config/asset_universe_sets.json). Counts mean any reported coverage overlap within the calendar period, not full-period coverage. The artifact is from workflow run #5 (artifact ID `11791697523`; SHA-256 `7484dddcad1e76224dca553ee8664900f51887f197afec966f27350388b0bec2`).
