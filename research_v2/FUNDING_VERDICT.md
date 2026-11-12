# FUNDING GATE v1 - VERDICT
Status: NOT RUN (stopped by decision; preconditions not established)
Date: 2026-11-12
This is neither an economic failure nor a pass. No economic run was executed.

Evidence (read-only audit, no files changed):
1. No FUNDING_VERDICT.md exists on origin/draft/funding-gate-v1-20261109.
2. No Funding files were found by the audited local filename/content search
   (patterns: fundingRate, funding_rate). Historical Funding coverage for
   three assets remains unverified.
3. The gate requires at least 3 assets. A third eligible asset has not been
   verified.
4. Feasibility of 300 resolved OOS trades has not been checked.
5. The runner CLI does not start the economic gate by itself; other call
   paths were not audited.

Decision: Gate v1 is not run. Reason is cost/scope: running it would require
collecting Funding history and selecting a third asset, which extends the
project. No parameter, threshold or cost assumption was changed.
Reopening requires a NEW hypothesis and a NEW protocol.
Remaining track: signal-bot forward test until 100 new trades.
