# OOS Multi-Horizon Economic Evaluation

This tool evaluates the profitability-first 5/10/20/50-bar forecast without lookahead.

It reads Project 60 JSONL only. For each evaluation timestamp t, the forecast sees bars through t and realized performance is measured at t+h. Economic trades are limited to VIABLE or STRONG forecast tiers.

Defaults:
- Capital: $500
- Round-trip cost: 0.35%
- Minimum history: 140 bars
- Evaluation step: every 10 Project 60 bars
- Horizons: 5, 10, 20, 50 bars
- Research only, live orders disabled

The report separates candidate_metrics (all directional forecasts) from economic_metrics (only economically viable/strong forecasts).

Metrics include trade count, win rate, gross/net PnL, expectancy, profit factor, max drawdown and average realized directional move.

Example on Termux:

    clear
    cd ~/market-intelligence-core
    python tools/oos_multihorizon.py --project60-file ~/institutional-flow/history/market.jsonl --symbols BTC,ETH --capital 500 --cost-pct 0.35 --step 10

This command does not start, stop, restart or modify protected legacy services or the Project 60 collector.
