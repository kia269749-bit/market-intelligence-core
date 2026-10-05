# Portfolio Risk Intelligence

Research-only portfolio-level risk diagnostics.

The module combines confidence, regime fit, measured edge and market regime into a bounded position-risk fraction. High-volatility regimes are deliberately scaled down.

Portfolio risk is checked in aggregate, with a separate correlation-penalty guard to avoid treating highly related positions as independent risk.

These calculations do not place orders, access exchange credentials, or control Termux services. They are inputs to research and paper/shadow analysis only.
