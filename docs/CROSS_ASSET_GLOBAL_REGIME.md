# Cross-Asset and Global Regime Intelligence

Research-only context layer for crypto analysis.

The module combines supplied returns for crypto, the US dollar, gold, equities and volatility into a coarse cross-asset regime:
- RISK_ON_CRYPTO_SUPPORTIVE
- RISK_OFF_CRYPTO_NEGATIVE
- DEFENSIVE
- MIXED

The module does not fetch data itself. This keeps data-source policy explicit and allows future connectors to supply authorized public observations without embedding credentials.

The macro adjustment is deliberately small and diagnostic. It must not override the existing signal-quality, profitability or risk gates by itself.

No live orders, exchange credentials, or Termux service control are involved.
