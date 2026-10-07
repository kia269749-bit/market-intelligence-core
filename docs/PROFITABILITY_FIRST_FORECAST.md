# Profitability-First Multi-Horizon Forecast

The brain must estimate opportunity before the economic gate evaluates whether an opportunity is worth taking.

This layer adds:

- 5, 10, 20 and 50 bar probabilistic path estimates.
- Historical analogue returns using only bars available before each historical forecast timestamp.
- Regime, trend and flow context.
- Expected return range, adverse move estimate and target-hit probability.
- Translation of forecast paths into $500 capital economics using the existing $4 minimum and $10 preferred targets.
- A best-horizon selector for opportunity discovery.

It does not guarantee future prices and does not place orders.

## Design rule

The economic gate must not be the forecasting engine. Forecast first, then calculate whether the forecast has enough expected move to overcome costs and reach the desired profit target.

This prevents a weak forecast from being turned into a signal merely because the threshold was loosened, while also preventing the system from treating a single short-horizon estimate as the entire market opportunity.

## Next integration

The live brain should consume forecast_path() and expose all horizons to the signal controller. A rejected immediate entry should remain observable as WATCH when a later horizon has a strong, validated path. Missed opportunities should be recorded against the forecast so threshold calibration can learn whether the gate is suppressing profitable setups.

Research-only and live-order-disabled behavior remain unchanged.
