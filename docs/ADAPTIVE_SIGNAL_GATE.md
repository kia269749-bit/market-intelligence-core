# Adaptive Thresholds, Signal Quality Gate and Kill Switch

Research-only controls for deciding whether an observed signal is strong enough to enter downstream analysis.

The quality gate checks score, confidence, measured edge, data quality, regime fit and signal decay. A signal must pass every configured check.

The adaptive threshold responds to recent score volatility but remains bounded. It does not learn from future observations.

The kill switch is a portfolio-level diagnostic based on peak-to-current drawdown. It does not execute orders or stop external services.

No exchange credentials, live orders, or Termux service control are involved.
