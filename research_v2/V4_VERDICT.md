# v4 economic verdict: REJECTED (2026-11-09)
Source: CI run 323 (id 42212356747), commit 0630706, release/v4-hyperliquid-verified-20261106.
OOS trades: 405 (81 per asset: BTC ETH SOL XRP DOGE), separate simulations, not one portfolio.
Net USD at 0.15% cost: -1103.14 | at 0.45% cost: -1709.14
All 5 assets: accepted=false, status=NO_TRADE. Per-asset samples below the 100-sample gate minimum.
ETH base +79.41 is small-sample, negative under strict (-40.59); not evidence of edge.
Gross edge before cost is also negative (about -0.4% per trade), so this is not a cost-accounting problem.
Funding coverage 100%, OI coverage 0, derivatives features disabled.
Decision: v4 closed. No threshold or model change after seeing this result. No demo of this strategy.
Remaining: one pre-registered Funding-feature test (gate fixed before run); signal bot forward test to 100 trades.
