# FOMO Outcome Validation

This module measures what happened after a detected FOMO event using a supplied future price path.

It reports terminal return, maximum favorable/adverse excursion, target/stop hit rates, and positive-return rate. It does not fetch data, trade, or assume that an event is profitable.

Validation must use real historical market data with strict event-time ordering to avoid look-ahead bias. Missing future observations should remain missing rather than being fabricated.
