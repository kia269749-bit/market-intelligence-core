# Daily + 4h Direction Evaluation Protocol v1

Status: PRE-REGISTERED BEFORE EVALUATION
Mode: Research only. No live orders.

## Objective
Compare daily-only, 4h-only, and combined daily+4h direction signals
for BTCUSDT and ETHUSDT.

## Data boundary
Input files are under:
data/real_oos_audit/long_history_20261011/

Only rows with timestamps strictly before 2025-01-01 00:00:00 UTC
may be parsed into the evaluation dataset. Stop reading at the first
row at or after this boundary. Never inspect or use later rows.

Do not synthesize missing candles. Do not silently repair invalid rows.
Do not delete suspicious returns merely because they are extreme.
Do not overwrite original data or existing reports.

## Decision time and target
A decision is made at the canonical end of a completed UTC daily candle.
The canonical end is computed from the candle-open timestamp (`ts`) plus
the expected interval length. Use the daily and 4h candles whose canonical
ends equal the decision time. Source `close_time` is audit-only: any mismatch
against the canonical end must be counted and reported by asset/timeframe.
This is a pre-evaluation protocol clarification prompted by the read-only
boundary audit; it does not alter source candles or synthesize missing rows.

The reference price is the completed daily close. The target is the
close of the next daily candle, only when its timestamp is exactly one
daily interval later. Label UP if the forward return is positive and
DOWN if negative. Exact-zero returns are excluded and counted.

## Fixed signal definitions
EMA periods are fixed at 50 and 200 for both timeframes.
UP means EMA50 > EMA200. DOWN means EMA50 < EMA200.
No parameter tuning is allowed on the evaluation period.
Indicators reset across gaps greater than 1.5 expected intervals.
Samples without valid indicator history or exact timeframe alignment
are excluded and counted.

Daily-only: daily EMA direction.
4h-only: 4h EMA direction.
Combined: issue a direction only when daily and 4h directions agree;
otherwise abstain. Report coverage as well as conditional accuracy.

## Temporal partitions
Development period A: decision times from 2020-01-01 through
2022-12-31 UTC.
Evaluation period B: decision times from 2023-01-01 through
2024-12-31 UTC.
No results from B may be used to tune rules.
No data from 2025 onward may be read or evaluated.

## Baselines
1. Majority direction computed only from A labels, separately per asset.
2. Persistence: sign of the most recently completed daily close-to-close
   return, using information available at the decision time.

## Metrics
For each asset and method, report sample count, coverage, accuracy,
balanced accuracy, and confusion matrix (TP, TN, FP, FN; UP is positive).
Report BTC and ETH separately. Also report the unweighted mean of the
two asset-level metrics; do not pool all rows as if they were independent.
Combined accuracy is conditional on non-abstained predictions; coverage
must always accompany it.

## Interpretation
This is a directional prediction experiment, not a profitability test.
Accuracy alone does not establish net returns or tradeability.
No claim of profitability or production readiness is permitted.

## Integrity and implementation
Use a new tool and new output paths. Preserve existing project files.
Record input SHA-256 hashes and the protocol version in the report.
Research-only remains true; live orders remain false.
