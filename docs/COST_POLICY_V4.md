# v4 Research Cost and Data Policy

## Cost convention

All policy rates are round-trip percentage points of notional. They are not decimal fractions.

- `base`: 0.15% round trip.
- `strict`: 0.45% round trip.
- The source of truth is `mi_core/cost_policy.py`.
- Research/economic evaluation paths default to `base` and accept the named `cost_mode="strict"` alternative.

A rate is selected once per evaluated trade. The base and strict rates are alternatives, never cumulative charges.

## Component diagnostics

`mi_core/costs.py` is a component decomposition tool for fee, spread, slippage, and impact sensitivity. Its default 11 bps estimate is not the v4 policy rate and must not be added to either policy mode.

`cost_model="components"` in the capital/profitability helpers is an explicit legacy or diagnostic alternative. It replaces the flat policy rate for that calculation; it is not stacked on top of it.

The active v3 live coordinator explicitly retains its pre-v4 component model. This isolates v4 research-policy changes from active v3 behavior.

## Derivatives data policy

Funding and open interest are not model inputs until their source, timestamps, freshness, and coverage are validated. Missing values are not zero and are not neutral evidence.

The v4 forecast feature set therefore excludes Funding/OI. The Project60 loader retains supplied raw values and reports per-asset coverage, but ranking and forecast features do not consume them. Re-enable only after a real, timestamp-aligned feed and coverage tests are available.

## Walk-forward reporting

Economic scoring uses non-overlapping, fully resolved OOS horizons. Per-asset results include a paired long-only Buy & Hold comparator and a deterministic random-direction comparator on the same OOS rows.

Summed per-asset fixed-capital diagnostics are not portfolio equity or a portfolio return. A true portfolio result requires synchronized positions, shared capital allocation, exposure limits, and portfolio-level execution/cost accounting.

All v4 validation remains research-only. It does not place orders or establish profitability.
