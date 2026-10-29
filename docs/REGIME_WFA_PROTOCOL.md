# Regime + ATR WFA protocol (research only)

This experiment is isolated from the active v3 path and from the original negative-result record in PR #115. It does not place orders.

## Frozen rules for this experiment

- The rolling forecast is sampled at the forecast horizon before applying any regime or direction filter, so rejected forecasts cannot create overlapping outcomes.
- The signal candle must close first. Entry is modeled at the next candle open.
- ATR uses a 14-bar true-range average. ADX uses 14-bar directional movement and a 14-value DX average. A signal is eligible only if ADX >= 22.
- Volatility is gated using ATR/close percent relative to the preceding rolling window's 10th and 90th percentiles. Current volatility is not used to compute its own thresholds. The filter requires at least 30 prior ATR-percent observations.
- Long/short stop and target levels use ATR and the known signal-candle-and-prior 20-bar swing low/high. Levels are fixed at entry and not moved after observing future prices.
- Exit is checked candle by candle for up to 24 bars. If stop and target are both touched in the same OHLC candle, the stop is assumed first.
- Realized historical funding events are charged according to side and holding interval using the existing model's nearest-prior-candle-close proxy for oracle notional. Events through the exit candle close are included conservatively because intrabar exit timestamps cannot be reconstructed from OHLC.
- Slippage is a fixed assumption (2 bps/side in CI), not measured historical fill data. Itemized fees/slippage/funding and fixed 0.15%/0.45% sensitivities remain separate.

## Required interpretation

This is a new hypothesis test, not a tuning loop and not evidence of an edge by itself. Record the exact commit, CI run, requested/observed candle boundaries, funding coverage, trade count, exits, costs, bootstrap intervals and limitations. A positive mean alone is insufficient: require a broader pre-registered multi-period WFA, sufficient independent trades/days, robust 1/3/7-day block intervals, realistic execution costs and portfolio-level risk tests before any edge claim. No real-money use is permitted based on this smoke test.

## Known limitations

- ADX here is a transparent rolling calculation, not claimed bit-for-bit identical to every charting platform's Wilder implementation.
- Candle OHLC cannot reconstruct order-book depth, true fills, liquidation or intrabar ordering.
- Funding cost uses a candle-close proxy for oracle price, not exact historical oracle marks.
- The 90-day single-asset run is a smoke evaluation. It is not enough to prove generalization or stable profitability.
