# pandas-ta-classic full-library scope audit
Date: 2026-11-22
Project: Project60 / EDGE_SEARCH_v1
Repository: `kia269749-bit/market-intelligence-core`
Branch: `research/edge-search-20261122`
Status: READ-ONLY SOURCE AUDIT; NO TRIAL REGISTRY CHANGE; NO DATA OR BACKTEST RUN

## Executive finding

The earlier estimate of **190 indicators + 70 patterns is not supported** by the current upstream package metadata. The current PyPI stable release is **pandas-ta-classic 0.9.0**, released 2026-10-28. Its published reference describes:

- **224 Category-system indicators and utility functions** across 10 categories.
- **62 native candlestick patterns** exposed by `cdl_pattern()`.
- **284 unique names after overlap correction**: `cdl_doji` and `cdl_inside` are included in both the 224 category count and the 62 pattern count, so 224 + 62 - 2 = 284.

The 224 count is not equivalent to 224 independent trading signals. It includes wrappers/accessors, candle transforms, performance/return metrics, statistical functions, math operators, rolling/index utilities, and helper functions. These require eligibility classification before any hypothesis is registered.

## Version provenance

- Package: `pandas-ta-classic`
- Stable release: `0.9.0`
- PyPI release date: 2026-10-28
- Published wheel: `pandas_ta_classic-0.9.0-py3-none-any.whl`
- Published wheel SHA-256: `f9792bfc478e6ab20dc67008eea748fd5f7042a986f96dbef582b270b706cc57`
- Upstream project: https://github.com/xgboosted/pandas-ta-classic
- PyPI release: https://pypi.org/project/pandas-ta-classic/0.9.0/
- Indicator reference: https://github.com/xgboosted/pandas-ta-classic/blob/main/docs/indicators.rst
- Changelog: https://github.com/xgboosted/pandas-ta-classic/blob/main/CHANGELOG.md

Important provenance distinction: GitHub Releases currently lists 0.8.32 as its latest tagged GitHub release, while PyPI lists 0.9.0 as the latest stable package. The 0.9.0 wheel hash above is therefore the immutable package-artifact identity for this audit. Do not claim a Git tag or source commit for 0.9.0 without separately verifying it.

## Category inventory reported upstream

| Category | Count | Audit note |
|---|---:|---|
| Candles | 5 wrappers | Includes `cdl_pattern`, `cdl_doji`, `cdl_inside`, `cdl_z`, `ha`; not five independent CDL patterns |
| Cycles | 8 | Hilbert/cycle indicators |
| Momentum | 53 | Oscillators and momentum functions |
| Overlap | 46 | Moving averages and price overlays |
| Performance | 3 | Drawdown and return metrics; not entry signals by themselves |
| Statistics | 14 | Statistical functions; several require benchmark/series context |
| Trend | 26 | Trend and direction functions |
| Volatility | 18 | Range/volatility functions |
| Volume | 20 | Requires valid volume; some functions also need OHLC |
| Math | 31 | Operators, transforms, rolling/index helpers; not standalone trading signals |
| **Total** | **224** | Category-system count |

The 62 native pattern names are listed in the upstream reference and are dispatched through `cdl_pattern(name=...)`. `doji` and `inside` have dedicated accessors and are the two overlapping names. `ha` and `cdl_z` are candle-related transformations, not CDL patterns.

## Look-ahead / non-causal audit

The upstream reference explicitly identifies the following forward-looking or whole-series behaviours:

1. `dpo()`: centered by default, shifting output backward. It is eligible only with `lookahead=False` or `centered=False`, fixed in the trial definition.
2. `ichimoku()`: Chikou and projected Senkou spans can contain future-relative values. Any signal may use only values actually observable at the signal timestamp; use `lookahead=False` and do not use future-shifted spans.
3. `cpr(virgin_cpr=True)`: virgin status depends on subsequent bars. Keep `virgin_cpr=False` and do not use a virgin flag in contemporaneous signals; `lookahead=False` is also documented.
4. `tos_stdevall()`: fits over the entire supplied series. No causal mode is documented; exclude from time-series signal trials.
5. `vp()`: aggregates the entire supplied series into price bins; it is a profile, not a causal per-bar signal. Exclude from time-series signal trials.

The documentation says `lookahead=False` is honored by DPO, Ichimoku, and CPR. It also documents tests that compare full-series output against shorter prefixes for registered indicators. This upstream documentation is evidence of the library's own stated contract, not an independent audit of this project's integration. Every candidate still requires project-level prefix-invariance tests using the exact pinned wheel and actual call parameters.

Additional eligibility checks before registration:
- `vwap` requires an ascending DatetimeIndex; exchange-session anchoring must be made explicit and consistent.
- Volume indicators must not treat missing/unknown volume as real zero volume. Validate source fields and document zero-volume behaviour.
- `beta` and `correl` require a benchmark/second series; define it before testing or mark them ineligible.
- Performance/return functions and math utilities must not be counted as independent trading signals unless a causal signal rule is explicitly defined.
- Multi-output indicators (e.g. MACD, Ichimoku, bands, PSAR, QQE) need a pre-registered deterministic rule for which output(s) produce the signal. Do not count each output column as a new indicator unless separately registered as a distinct hypothesis in advance.
- Candle patterns are computed from completed OHLC bars. A pattern observed at candle close may only execute at the next eligible bar, never at that same candle's earlier price.

## Provisional full-library scale (not a locked trial count)

If one naively treated all 284 unique documented names as candidates across 15m, 1h, 4h, and 1d, and LONG_ONLY / SHORT_ONLY, while keeping BTCUSDT, ETHUSDT, and SOLUSDT as one portfolio unit per trial:

`284 × 4 timeframes × 2 directions = 2,272` provisional portfolio trials.

This is only a scale estimate, **not an approved registry**. It overcounts non-signal utilities and functions that need extra inputs, and it does not yet apply the causal/eligibility review, output-rule definitions, or duplicate-family grouping. The final eligible candidate count can only be produced by a version-pinned callable inventory and explicit per-function eligibility table.

For comparison, using the unverified 190 + 70 estimate would have implied 2,080 raw trial rows under the same timeframe/direction assumptions. That estimate is superseded by the verified package metadata and must not be used.

## Conflict with the currently locked EDGE_SEARCH_v1 registry

The current EDGE_SEARCH_v1 lock is:
- 140 portfolio rows (138 indicator portfolios + 2 Kronos portfolios).
- 23 indicator definitions.
- Timeframes: 1h, 4h, 1d.
- Assets: BTCUSDT, ETHUSDT, SOLUSDT.
- LONG_ONLY / SHORT_ONLY.
- Holm correction across the entire 140-row registry.
- No additions after lock.
- Locked `TRIALS.json` blob SHA-1: `f98f648706d4537b6e40747f0d490859aff8a629`.

Therefore, importing the full library into this existing registry would directly violate the frozen-trial rule and invalidate the current lock. This audit does **not** edit `TRIALS.json`, change the 140-row scope, or silently add 15m, patterns, or parameter variants. The current 140-row protocol remains unchanged and its data/economic status remains NOT RUN.

If the project elects to replace the 140-row experiment with a full-library experiment, that must be a separately versioned protocol and a new pre-data registry lock. It must define:
1. Exact package artifact and checksum (0.9.0 wheel SHA-256 above, or another explicitly selected immutable artifact).
2. A complete function-level inventory and eligibility/exclusion reason for every callable.
3. Explicit output-to-signal rules and fixed parameters for every multi-output function.
4. Causal-prefix tests and next-bar execution for every retained function/pattern.
5. Exact timeframes, assets, directions, and resulting full hypothesis count.
6. Holm correction across every row in that new locked registry, with no post-lock additions.
7. Existing A/B/C sealing, independent-cluster, cost, drawdown, concentration, and minimum-evidence rules retained unless explicitly superseded before data access.

## Execution state

- Upstream metadata and reference inspected: YES.
- Exact package release and wheel checksum identified: YES.
- Function-by-function runtime introspection against the wheel: NOT RUN.
- Project-level causality tests: NOT RUN.
- Candidate eligibility table: NOT YET BUILT.
- New full-library registry: NOT CREATED.
- Existing 140-row registry: UNCHANGED.
- Futures data download: NOT RUN.
- Backtests / Holm / bootstrap / economic verdict: NOT RUN.
- No bot, forward-test, Termux service, or live system was changed.

## Sources

- PyPI 0.9.0 release and wheel metadata: https://pypi.org/project/pandas-ta-classic/0.9.0/
- Current PyPI project metadata: https://pypi.org/project/pandas-ta-classic/
- Upstream indicator reference: https://github.com/xgboosted/pandas-ta-classic/blob/main/docs/indicators.rst
- Upstream changelog: https://github.com/xgboosted/pandas-ta-classic/blob/main/CHANGELOG.md
- Upstream GitHub releases: https://github.com/xgboosted/pandas-ta-classic/releases
