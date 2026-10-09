# External strategy research queue

This document records outside research leads before any strategy is promoted into the
Market Intelligence signal stack. Published or repository-reported profitability is a
hypothesis to test, not a promise or a reason to bypass our gates.

## Research leads reviewed on 2026-10-09

1. **Systematic Crypto Research (GitHub, MIT software license):**
   https://github.com/PeterLP123/systematic-crypto-research
   - Compares volatility-normalized multi-asset trend-following with BTC-dominance
     mean reversion using Binance and FRED data.
   - Its frozen trend-following run reports +9.54% net return over a 263-day
     post-selection window, while the mean-reversion candidate reports -6.96%.
   - Important caveats from the project itself: trend exposure is concentrated in
     BTC; the window is limited; the mean-reversion strategy has too few entries;
     its post-hoc relative-value variant has only six entries and is explicitly not
     deployable. We use the methodology and strategy family as a research lead, not
     copied performance claims.

2. **Gbadebo (2026), “Momentum Trading in Cryptocurrencies: A Comparative Study of
   Time-Series and Cross-Sectional Strategies”:**
   https://doi.org/10.15388/batp.2026.1
   - Studies eight major crypto assets from 2020-01-01 through 2025-10-31 using
     multi-horizon EMA momentum and volatility normalization.
   - The abstract reports stronger results for time-series momentum than
     cross-sectional momentum, but the published headline returns are not a
     guarantee of current performance and require independent reproduction.

3. **Arain & Snudden (2025), “When Are Statistical Forecast Gains Economically
   Relevant? Evidence From Bitcoin Returns”:**
   https://doi.org/10.1002/for.70077
   - Uses out-of-sample Bitcoin forecasts and macro/other-market predictors.
   - Its central lesson is that average directional accuracy alone does not ensure
     profitability; predictive performance must remain stable during large moves.
   - The USD index and Shanghai equity index are reported as promising predictors in
     that sample. This motivates a separate future cross-market feature test with
     strict timestamp alignment, rather than assuming the relationship persists.

4. **Crypto momentum vs mean-reversion repository:**
   https://github.com/mhtkrmz/crypto-alpha-comparison
   - Compares multi-asset trend following with cross-sectional mean reversion under
     shared portfolio and cost assumptions.
   - Its README reports trend following outperforming mean reversion in its sample,
     while explicitly warning that portfolio funding and exposure assumptions can
     exaggerate results.

## Reproducible local tournament

tools/external_strategy_tournament.py tests six fixed, non-optimized candidates on
real daily OHLC data:

- Buy-and-hold benchmark
- 200-day simple moving-average trend filter
- EMA 20/50 trend filter
- Seven-day time-series momentum, long/short
- 20-day Donchian breakout with 10-day exit
- RSI(14) mean reversion, enter below 30 and exit above 50

The workflow downloads up to 2,500 daily candles for BTC, ETH, SOL, BNB and XRP
from Binance public market data. It reports a chronological 70% development /
30% holdout split and repeats the same fixed rules under 0.20%, 0.35% and 0.50%
round-trip cost assumptions on $500 starting capital.

No parameter search is performed. Signal decisions use completed daily closes and
are delayed before the next executable interval. Results are diagnostics, not an
acceptance decision. All outputs retain research_only=true, live_orders=false
and trade_ready=false.

## Promotion gates

A candidate must not be promoted because it won one backtest or beat another weak
candidate. Before integration into production signal selection it must demonstrate:

- Positive net expectancy after fees, spread/slippage and, for perps, funding.
- Positive results across more than one untouched chronological window and more
  than one market regime.
- Stability when the single best trade is removed and under cost stress.
- Enough independent completed trades to support inference.
- No lookahead, timestamp leakage, survivorship or overlapping-capital accounting.
- A live shadow/paper record before any consideration of real orders.

## Cross-market macro experiment

The same research branch now includes tools/cross_market_macro_research.py and a
GitHub Actions job that downloads public FRED daily series for the broad USD index,
S&P 500, gold, WTI oil and VIX, then aligns them to BTC daily OHLC data. Macro changes
are lagged by at least two calendar days relative to the BTC candle date. A fixed OLS
model is fit only on the first 70% of aligned observations and evaluated on the final
30%, with both direction-only and cost-thresholded results compared against
buy-and-hold. This is an exploratory test of whether other markets add information,
not a signal accepted into the production brain. The external-data job must pass and
its holdout results must be reviewed before any conclusion is drawn.
