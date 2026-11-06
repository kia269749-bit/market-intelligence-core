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

The active v3 live coordinator explicitly retains its pre-v4 component model. This isolates v4 research-policy changes from active v3 behavior. The shadow journal also retains its historical 0.35% fallback for legacy records that do not carry a recorded cost; new v4 research evaluations must store the selected policy mode and rate explicitly.

## Derivatives data policy

Funding and open interest are not predictive model inputs. Missing values are not zero and are not neutral evidence.

The primary WFA data source is Hyperliquid perpetual candles plus discrete historical funding events. `mi_core/hyperliquid_data.py` writes Project60 JSONL, preserves event timestamps and freshness, and aligns funding strictly before candle close. Funding is used only as a holding-period cashflow in economic scoring, not as a forecast feature. The 0.15%/0.45% rates represent round-trip execution costs; discrete funding cashflows are applied separately for the exact holding interval and are not counted as a second transaction fee. A WFA run cannot pass its economic acceptance gate unless fresh funding coverage is at least 95%.

Hyperliquid's public historical feed does not provide the historical OI series required for this WFA. OI therefore remains explicitly absent, excluded from model features, and excluded from the adaptive strategy universe. The optional Binance USD-M Futures adapter is retained for environments where its public endpoint is reachable, but GitHub Actions received HTTP 451 from the Binance Futures endpoint during the integration run; its data is not used for official WFA claims. Binance's historical OI endpoint is also limited to the latest 30 days, so it cannot supply full-history OI for a long 1h test.

Example Hyperliquid collection command (writes a new file and refuses to overwrite a non-empty file):

```bash
python -m mi_core.hyperliquid_data --coin BTC --asset-key BTCUSDT --interval 1h --bars 8000 --out data/real/btcusdt_hyperliquid_project60.jsonl
```

## Walk-forward reporting

Economic scoring uses non-overlapping, fully resolved OOS horizons. Per-asset results include a paired long-only Buy & Hold comparator and a deterministic random-direction comparator on the same OOS rows. Acceptance additionally requires the model to beat both baseline net profits and the random baseline to pass a 5% Holm-adjusted one-sided test across evaluated assets for that horizon.

Summed per-asset fixed-capital diagnostics are not portfolio equity or a portfolio return. A true portfolio result requires synchronized positions, shared capital allocation, exposure limits, and portfolio-level execution/cost accounting.

All v4 validation remains research-only. It does not place orders or establish profitability.
