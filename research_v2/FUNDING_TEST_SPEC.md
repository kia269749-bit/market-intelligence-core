# Funding feature implementation specification

The locked economic rules in `research_v2/FUNDING_GATE_v1.md` are authoritative. This change is technical implementation only, not an economic run or verdict.

- Research only; `live_orders=False`. No secrets, live orders, demo/testnet, or Kronos.
- No workflow added or modified. No push to main or release branches.
- Legacy `join_funding_feature` and `project60_rows` are unchanged.
- Model feature source is exclusively fetched `FundingEvent` history.
- Per candle, use the latest event with timestamp `<= candle.close_time_ms`. Exact-close included; +1 ms excluded.
- One raw Funding rate is appended as column seven. No average, window, conversion, normalization, lag, or extra parameter. Missing values are zero-filled only at model input; the alignment helper preserves None.
- The six existing v4 features, labels, fitting and output remain the same when disabled. Disabled is the default and must exactly match the v4 path on a deterministic fixture.
- Enabled mode requires one aligned Funding value per bar and fits seven-column rows.
- Tests: timestamp boundary, seven-column model input and prediction change, self-contained disabled parity.
- CI: `.github/workflows/ci.yml` runs `python -m unittest discover -s tests -v` for PRs. `v4-research-validation.yml` also contains this command, but its PR filter targets main only and therefore does not run for PR #130's release-base target. No workflow is changed.
- This work does not run economic WFA, portfolio evaluation, statistical comparisons, or Funding Gate acceptance. Those require the separately authorized economic workflow.
