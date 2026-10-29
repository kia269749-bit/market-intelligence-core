# Cost Policy Protocol v4 (Research Only)

Status: specification introduced on branch `codex/central-cost-policy-v4`. This document does not claim that all existing modules have been migrated or validated.

## Locked assumptions

- Base round-trip cost: **0.15%** of notional.
- Strict round-trip cost: **0.45%** of notional.
- Values are percentage points: for $500 notional, the modeled cost is $0.75 base and $2.25 strict.
- The strict scenario is a sensitivity/stress case, not an additional charge to stack on top of the base case.
- Active v3 behavior must remain unchanged. v4 work is isolated to this branch until reviewed and validated.

## Required integration rules

1. Use one policy object as the source of truth for the two round-trip scenarios.
2. Callers must state whether they use base or strict cost; avoid hidden per-module defaults.
3. Preserve gross PnL, modeled cost, and net PnL as separate reported values.
4. `trade_economics.evaluate_capital_target` uses the central fixed-rate policy by default; `strict_cost=True` selects 0.45% instead of 0.15%.
5. Its `cost_model="components"` mode is an explicit alternative legacy decomposition for comparison only. Never combine that component total with the fixed round-trip percentage.
6. `mi_core.costs.estimate_execution_cost` remains a separate component estimator; its fee/spread/slippage assumptions are not yet validated as an LBank-specific schedule and must not be presented as the central policy.
7. Report the market-data venue and the assumed execution-cost venue separately. Current project intent is Hyperliquid perpetual market data with LBank Futures cost assumptions; do not silently infer that exchange-specific fee schedules are identical.
8. No live orders or account actions. This is research-only.
9. Validate on chronological out-of-sample data, with no look-ahead, duplicate trade counting, or overlapping outcome windows misrepresented as independent evidence.
10. A green unit-test suite establishes software behavior only, not a profitable trading edge.

## Migration checklist

- [x] Add explicit versioned policy object and unit tests.
- [x] Route `trade_economics.evaluate_capital_target` through the central policy by default, preserving component mode as an explicit alternative.
- [ ] Decide and test whether `mi_core.costs` should expose a policy-based API or remain a component-only estimator.
- [ ] Remove legacy 0.35% defaults only from v4 paths after each caller is tested.
- [ ] Add cross-module tests proving base/strict selection is consistent.
- [ ] Run the complete GitHub Actions suite and inspect results.
- [ ] Review diffs before considering a pull request.
