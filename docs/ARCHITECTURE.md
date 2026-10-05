# Architecture

1. Data: append-only raw observations and normalized MarketBar.
2. Features: returns, moving averages, volatility, order imbalance and z-scores.
3. Flow: buy/sell pressure, OI/funding context and trade-flow features.
4. Smart Money: whale bias and historical trader quality scoring.
5. FOMO/Meme: momentum, volume, sentiment and early-strength scoring.
6. Regime: BULL, BEAR, RANGE and HIGH_VOL states.
7. Signals: explainable score with reasons and confidence.
8. Validation: transaction costs, walk-forward/OOS, Monte Carlo and anti-overfitting.
9. Risk: position sizing, max drawdown and kill switch.
10. Shadow: signal/outcome persistence without live execution.
11. Reporting: machine-readable output suitable for dashboard and AI brain.

The repository is independent from the four legacy Termux services and contains no service-control code.
