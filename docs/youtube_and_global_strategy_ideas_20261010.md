# YouTube and global strategy ideas for Market Intelligence Core
Date: 2026-10-10
Status: research queue only; no strategy promotion or live trading.

## What to borrow from YouTube and public trading projects

### A. Volume Profile + Order Flow / Footprint
Reference videos/resources:
- BikoTrading, "My OrderFlow Trading Strategy! Volume profile + Footprint": https://www.youtube.com/watch?v=fJumu2qKIsQ
- Wysetrade, "Ultimate Volume Profile Trading Strategy": https://www.youtube.com/watch?v=CrHdBH6yBJ8
- GoCharting's free Order Flow education course (bid/ask, delta, footprint, market profile, VWAP): https://gocharting.com/education/courses/orderflow-tutorial
- Background summary on volume profile + order-flow confirmation: https://videohighlight.com/v/yjsFVPGCsdY

Testable hypotheses (not assumed truths):
1. At a prior-session high-volume area / value-area edge, require price rejection or acceptance plus order-flow confirmation before taking a mean-reversion or breakout entry.
2. Define absorption only from timestamp-aligned executed trades and book changes, not from a large candle or volume bar alone.
3. Compare price-only entry against price + delta/imbalance confirmation, using identical exits, risk sizing and out-of-sample windows.
4. Record whether the confirmation improves net expectancy, drawdown and false-break rate after costs, not just win rate.

Data requirement: intraday OHLCV plus historical trade prints (aggressor side if available), and preferably timestamped order-book snapshots/updates. Daily candles cannot validate footprint, tape speed, queue position or historical spread. Do not retrofit these signals into daily OHLC results.

### B. Periodic walk-forward selection with a cash fallback
Reference implementation/research:
- https://github.com/AKzar1el/walk-forward-crypto

Its documented design periodically ranks a fixed set of trend, breakout, mean-reversion and cash candidates using a trailing window net of costs/funding, then trades a small ensemble out of sample. It also documents failures, model-selection uncertainty, and dependence on regime.

Testable adaptation:
1. Keep the candidate family list fixed before each walk-forward run.
2. At each rebalance date, rank only using data strictly before that date and net of costs/funding.
3. Select a small top group only when its trailing score is positive and the minimum trade/sample threshold is met; otherwise hold cash.
4. Freeze the chosen group for the next period; no mid-period retuning.
5. Compare with buy-and-hold, SMA200, EMA20/50, Donchian, current fixed blends and always-cash.
6. Repeat across multiple rolling windows and a later frozen replay. Report each window, not just pooled results.

Caution: the source project's reported returns are self-reported paper/research results, not audited guarantees. We borrow the validation structure, not its headline performance.

### C. Preserve current positive blend results as candidates, not as proof
The current 2,500-bar daily OHLC experiment reported positive holdout PnL for both combined strategies across five assets at some/all tested costs, but the blends were created during this research cycle and the same holdout has now influenced design decisions. It is no longer a clean untouched final test. Max drawdown remains high for some assets, especially XRP.

Next action:
- Freeze the existing blend formulas and parameters.
- Do not use this holdout to tune or select thresholds further.
- Run a new, later/frozen replay and several rolling walk-forward windows.
- Add volatility-normalized sizing and a portfolio-level exposure cap as a separate ablation, with the same signals and next-open execution.
- Require positive net expectancy after costs, robustness at 0.35% and higher stress, acceptable drawdown, enough independent trades, and a shadow/paper period before promotion.

### D. Execution realism from educational material
Reference: https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy
- Model fees according to order type, and do not assume maker fees when a strategy would cross the spread.
- Include spread, slippage, funding for perps, liquidity/partial-fill risk, and higher costs for thin meme coins.
- For DEX meme tokens, separately consider gas, price impact, failed transactions, transfer restrictions and MEV; candle OHLC cannot validate these effects.

## Decision
Priority 1: new frozen walk-forward test of the current positive blends + volatility sizing.
Priority 2: implement a separate data-gated Volume Profile/Order Flow feature experiment only once adequate historical intraday data is available.
Priority 3: keep Project60 flow/OI/funding and FOMO wallet-following evidence as timestamped independent features; test incremental value by ablation.
All work remains research-only, live_orders=false, trade_ready=false. No protected Termux services touched.
