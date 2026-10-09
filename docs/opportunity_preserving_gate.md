# Opportunity-preserving profitability gate

This layer is a selector/ranker, not a signal suppressor.

Design rules:
- Keep directional opportunities when evidence is incomplete.
- Reject only hard failures: non-directional output, critically low data quality/confidence,
  or a clearly demonstrated expected-move-versus-cost failure.
- When cost inputs are unavailable, mark economics as UNAVAILABLE and keep the opportunity visible.
- Rank STRONG, GOOD, WATCH, and EARLY_OPPORTUNITY rather than collapsing everything below one threshold.
- Feed outcomes back later so weak contexts lose weight instead of suppressing the whole signal family.

The $20,000/month objective remains a research target only. Any claim toward it must survive
net-cost, out-of-sample, walk-forward, and robustness validation. Live order execution remains disabled.
