# Trader-skill and day-trader-skill reuse audit

Date: 2026-10-24

Upstream repositories:
- https://github.com/Jakeschincariol/trader-skill (MIT)
- https://github.com/Jakeschincariol/day-trader-skill (MIT)

This project is not installing Claude skills as runtime dependencies. It is
adapting selected engineering ideas into ordinary Python modules that can run
under Termux, be tested offline, and remain disconnected from order execution.

## Findings from source inspection

### Reuse now, in research-only form

- **Explicit strategy setup and closed-bar timing:** the upstream ORB uses a
  completed candle close beyond the opening-range high, not a wick touch. The
  project adapter is mi_core/day_trader_orb.py; callers must provide complete,
  chronologically ordered OHLC bars and define the session for 24/7 futures.
- **Conservative path replay:** same-bar stop/target ambiguity resolves
  stop-first, and a gap through the stop uses the worse opening price.
- **Cost-aware sizing and net results:** PR #105 adds estimated round-trip
  costs to planned stop risk. The ORB adapter uses the central cost assumptions
  (6 bps taker fee + 2 bps spread + 3 bps slippage + 1 bp impact per side =
  24 bps round trip), with 1x/1.5x/2x sensitivity multipliers. The fee is a
  published default, not yet account-specific verified.
- **Time-Machine-inspired robustness check:** mi_core/trade_bootstrap.py
  resamples already-net realized trade outcomes using a deterministic,
  circular moving-block bootstrap. It reports the distribution of total net
  P&L, expectancy and maximum drawdown. It intentionally does not refit a
  strategy or pretend simulated paths are predictions. Apply costs upstream
  exactly once before supplying trade outcomes.
- **Fail-closed validation:** malformed, non-finite, or out-of-order inputs
  should be rejected, not silently repaired or treated as zero.
- **Paper-first / human approval boundary:** upstream separates strategy
  analysis, risk approval and broker ticket generation. Preserve that
  separation when a future exchange executor is designed.

### Candidate strategy ideas, not yet accepted as trading edges

The day-trader scanner describes 20-day closing-high breakout, bull flag,
moving-average reclaim, RSI oversold and oversold bounce setups. These are
hypotheses to register and test on the project's actual futures data, not
signals to enable automatically. For crypto, the stock market's opening bell
and equity session calendar do not transfer directly. A crypto ORB needs a
pre-registered UTC session definition and must be compared with simple
trend/momentum baselines and no-trade.

ATR-based stops and fixed-R targets are useful configurable research variants,
but should be evaluated as a preregistered parameter family with multiple-
testing controls, not tuned against the final holdout.

### Execution safeguards to implement before any real orders

The upstream risk gate checks each order and the cumulative batch, checks
fresh prices and stops, blocks duplicates, caps per-trade and daily loss,
limits order/trade counts, and binds approval to a fingerprint of the exact
order that passed risk. These are strong architectural patterns for a future
executor. They are not a reason to enable an order path now.

Before any exchange execution module is eligible, it must also reconcile
actual positions and open orders with the exchange, use idempotent client
order IDs, handle partial fills/timeouts/retries, protect API keys, enforce
a kill switch and daily loss cap, and prove that a stale risk approval cannot
be reused after the order changes.

## Statistical caveats

The upstream README's illustrative TSLA replay reports 33 historical triggers
over 59 sessions, with 13 target hits, 15 stop hits, 5 unresolved and average
-0.062R. Its 10,000 simulated paths report 29.4% target-first, 25.5%
stop-first and 45.1% unresolved, with average +0.034R. Those are upstream-
published example figures, not results on this repository's data. The large
unresolved fraction and divergence from historical results demonstrate why a
Monte Carlo verdict alone is not evidence of edge.

The new bootstrap module works on observed net trade outcomes and reports
sensitivity to resampling. It cannot account for missing regimes, structural
changes, or dependence longer than the selected block length. It is
supplementary to, never a replacement for, chronological walk-forward/OOS
evaluation, realistic fills, funding, cost stress, baselines and multiple-
testing controls.

## Scope and safety

- Research only: no network, broker, order, or live-signal side effects in the
  new bootstrap module.
- No new live-order setting or central fee assumption is changed.
- No strategy is approved for trading by this audit.
- Existing upstream MIT license and attribution should be preserved if any
  upstream source code is copied verbatim. The new bootstrap implementation
  is an independent adaptation of the general resampling idea.
