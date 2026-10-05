# Cross-Asset Signal Gate Integration

The macro gate adds cross-asset context to signal quality without replacing the existing signal-quality, profitability, portfolio-risk, or kill-switch gates.

A risk-on regime modestly favors LONG signals; a risk-off regime modestly favors SHORT signals. Mixed and defensive conditions receive conservative fit scores.

The adjusted quality is bounded to 0..1 and the result is explicitly diagnostic-only. This layer does not place orders, change exchange configuration, or control Termux services.
