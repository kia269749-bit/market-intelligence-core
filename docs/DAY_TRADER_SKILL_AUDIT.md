# Day-trader-skill audit and research adaptation

Date: 2026-10-24

Upstream: https://github.com/Jakeschincariol/day-trader-skill
License: MIT (retain attribution/license if copying upstream code; this project instead implements a small independent research adapter).

## What the upstream actually does

The public repository has 11 Claude skills for US equities: scanner, news, entry timer, exit planner, time-machine replay, risk, budget sizing, broker ticket handoff, alerts, earnings analyst, and public congressional-trade disclosures. Its data tools use public Yahoo Finance chart endpoints, Nasdaq symbol lists, SEC EDGAR and House Clerk disclosures. The example uses TSLA 5-minute bars, a 15-minute opening range, a midpoint stop, 1R target and an end-of-day exit. The broker workflow is approval-gated and paper-first, but it is not a futures adapter.

## Important empirical finding from its own published example

The README's own TSLA example reports a 59-session historical replay with 33 triggers: 13 targets, 15 stops, 5 neither, and average return -0.062R. Its 10,000 simulated paths report 29.4% target first, 25.5% stop first and 45.1% neither, with average +0.034R. Nearly half the simulated paths are unresolved at the close, and the simulation does not establish positive net returns after fees, spread and slippage. These are upstream-published example figures, not a run performed on this project's data. Source: upstream README and tests/test_timemachine.py.

## Adaptation in this project

Added `mi_core/day_trader_orb.py`, a research-only opening-range-breakout replay for caller-supplied OHLC bars with explicit session IDs. It uses the project's central LBank Futures cost assumptions by default (6 bps taker fee + 2 bps spread + 3 bps slippage + 1 bp impact per side = 24 bps round trip), supports cost multipliers, records gross/net P&L and expectancy, sizes positions to a default 1% capital risk budget subject to a 25% notional cap, and conservatively treats same-bar stop/target ambiguity as stop-first. Stops account for an opening gap beyond the stop. It produces diagnostics only; it cannot send orders and does not modify live signal tiers.

Because crypto futures trade 24/7, the caller must define the session window explicitly; a US stock opening bell cannot be assumed to map directly to crypto. This implementation only tests a generic session-based ORB hypothesis and does not fetch or fabricate historical market data.

## Limitations / acceptance criteria

- No verified multi-session OHLC history was available in this integration step, so the strategy has not been economically validated on real Project60 data.
- Unit fixtures test mechanics and cost accounting, not profitability.
- Before any PASS: use complete timestamped historical bars, document session boundaries and symbol mapping, account for missing bars and funding where applicable, compare against no-trade and simple baselines, use chronological walk-forward/OOS, report trade count, net expectancy, profit factor, drawdown and cost stress at 1x/1.5x/2x, and prevent parameter tuning on the final holdout.
- The central cost model is a published-default estimate; account-specific LBank fees remain unverified.
- No exchange adapter, broker, order path, live brain decision, or `live_orders` setting is changed. The strategy remains research-only.
