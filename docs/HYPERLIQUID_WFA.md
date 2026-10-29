# Hyperliquid Perpetual WFA (research-only)

This branch adds a separate entry point for historical walk-forward evaluation using Hyperliquid perpetual candle data and historical funding events. It does not change the existing v3 execution path, place orders, or use account credentials.

## Run

The command accepts UTC epoch milliseconds. Use a range whose coverage you can independently verify; the API response is reported with its observed first and last timestamps.

    python -m mi_core.hyperliquid_wfa --coin BTC --interval 1h --start-ms 1735689600000 --end-ms 1767225600000 --horizon 24 --train-window 300 --min-train 60 --slippage-bps-per-side 2 --bootstrap-resamples 10000 --block-days 1 --out reports/hyperliquid_btc_1h_wfa.json

The example dates are an example range only. Do not treat the command as proof that the run has been executed or that the requested history is complete.

## Primary itemized cost model

- **Fees:** defaults to the public base-tier perpetual rate, 0.045% per taker side or 0.015% per maker side. Actual account fee tier, referral/staking discounts, maker rebates, and execution type may differ. Override these assumptions when verified account-specific rates are available.
- **Funding:** uses historical fundingHistory events in the position's actual holding interval. Positive funding is a cost to a long and a credit to a short; negative funding reverses that direction.
- **Funding price limitation:** Hyperliquid funding uses oracle-price notional. The candle endpoint does not supply historical oracle price for each event, so this implementation uses the nearest prior candle close as a clearly labelled proxy. Results are not oracle-exact.
- **Slippage limitation:** slippage_bps_per_side is an explicit model assumption, not observed historical execution slippage. Candle OHLC data alone cannot reconstruct historical bid/ask depth or actual fills. Do not describe this as measured slippage.
- **No double counting:** itemized fees + slippage + funding are the primary net-return estimate. Fixed 0.15% base and 0.45% strict cost cases are reported separately as sensitivity diagnostics and are not added to the itemized costs.
- **Return basis:** returns are measured as percentage of entry notional for one-unit exposure. This is not a portfolio/equity curve, not a liquidation simulation, and not a real account drawdown calculation.

## WFA and dependence

The existing rolling walk-forward forecaster is reused, with its training labels restricted to mature outcomes. The evaluation samples the full forecast timeline at the horizon interval before filtering directional predictions, preventing FLAT predictions from accidentally making trades overlap. Confidence intervals use a deterministic contiguous UTC-day block bootstrap; increase --block-days to examine multi-day dependence. A single observed day returns INSUFFICIENT_DAYS rather than a misleading confidence interval.

## Required validation before any edge claim

1. Run the unit suite and review the CI result.
2. Execute the command on a verified, sufficiently long Hyperliquid history; save the JSON output and record the exact date range, API response coverage, model version, fee tier assumptions, and slippage assumption.
3. Compare itemized net returns with the separate 0.15% and 0.45% policy sensitivities.
4. Add a historical oracle-price source and historical executable spread/depth or fill-based slippage before calling funding-price and slippage estimates exact.
5. Evaluate portfolio-level concurrency, position sizing, liquidation/margin effects, and cross-asset dependence separately before interpreting trade-level results as portfolio profitability.

## Scope boundary: Telegram forward test

The Telegram bot files (telegram-bot, including its dynamic-state hash manifest and append-only signal archive) are a separate codebase. This repository cannot safely implement or verify that bot's hash exclusions or signals_history.json writer dependency. Those changes require a separate reviewed change in the Telegram bot repository; no bot service, bot code, or bot history is modified by this branch.

## Status language

This runner is a new implementation, not a result. Until a real data run and CI evidence are recorded, there is no claim of successful Hyperliquid WFA, positive expectancy, or trading edge. Everything remains research_only=true and live_orders=false.
