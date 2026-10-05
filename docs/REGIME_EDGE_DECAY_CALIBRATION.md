# Regime Edge, Signal Decay and Calibration

This research-only stage measures whether an observed signal edge is specific to a market regime, how returns change across forward horizons, and whether confidence scores are calibrated against observed win rates.

## Regime-specific edge
Observations are grouped by regime. A minimum-sample gate prevents tiny groups from being treated as proven edges. A positive edge requires both positive mean return and win rate above 50%.

## Signal decay
Returns are grouped by explicitly supplied forward horizon. The analysis reports the best observed horizon and decay from that peak to the latest horizon. It does not manufacture missing horizons or use future data outside the supplied observations.

## Calibration
Confidence values are bucketed into configurable bins and compared with observed win rate. calibration_error is a sample-weighted absolute confidence gap. This is diagnostic only and should not be used as an automatic trading rule.

No exchange credentials, live orders, or Termux service control are involved.
