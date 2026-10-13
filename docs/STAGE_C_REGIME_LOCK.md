# Stage C structural regime-window lock

Status: frozen before any Stage C strategy performance computation or inspection.
Applies to the development interval only: 2020-10-05 through 2025-07-29 inclusive.
No final-holdout data may be loaded or inspected. Never use `final-step` or any alias.
Research controls remain `research_only=true` and `live_orders=false`.

## Rule

Partition the full, fixed development calendar interval into three consecutive, non-overlapping calendar-time bins as equal in elapsed UTC days as possible. The interval has 1,759 days. Allocate 586 days to bin 1, 586 days to bin 2, and the remaining 587 days to bin 3. These boundaries depend only on the preregistered date range, not on prices, returns, volatility, strategy performance, or coverage.

- Regime window 1: 2020-10-05 through 2022-05-13 inclusive (586 days).
- Regime window 2: 2022-05-14 through 2023-12-20 inclusive (586 days).
- Regime window 3: 2023-12-21 through 2025-07-29 inclusive (587 days).

Use these exact date windows for every strategy and benchmark. Do not shift boundaries to align with market conditions or improve results. If a series has no valid observations in a bin, report it as unavailable for that series; do not redefine the bin. Report calendar-year results separately as specified in the preregistration, but do not substitute calendar years for these three fixed bins in the candidate gate.

## Integrity

This is a structural partition of the development calendar only. It is not a claim that the bins correspond to bull, bear, or sideways markets. No strategy performance has been computed or inspected to define this rule. Commit this lock before building or running performance evaluation code.
