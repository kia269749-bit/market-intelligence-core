# Stage B: locked chronological holdout

The calendar lock spans 2020-10-05 through 2026-10-12 inclusive: 2,199 calendar days.
Development is 2020-10-05 through 2025-07-29 inclusive (1,759 days). The untouched final holdout is 2025-07-30 through 2026-10-12 inclusive (440 days). The final segment is about 1.2 years and represents only one market regime; this materially limits confidence in any final result.

The lock file is `config/final_holdout_lock.json`. Its SHA-256 is recorded in the Stage B PR description/commit report and must be verified against the committed bytes. Development mode stops reading the sorted CSV at the first date on/after the holdout boundary. Final holdout access requires the explicit `step="final-step"` call. The regression test places a poison row after the boundary to verify it is not returned or traversed past the boundary.

The 30-asset universe is the currently listed Binance USDT spot universe from the coverage audit. It has survivorship bias: delisted/failed assets are absent. The 22-asset >=5-year subset is a robustness comparison, not a cure for survivorship bias. Daily OHLC coverage does not provide historical spread or slippage.

Year/month availability reports must be computed from the actual coverage artifact using `availability_counts`; do not infer coverage from today's listing or replace missing rows with zeros. A missing/unavailable artifact must be reported as unavailable, not fabricated.
