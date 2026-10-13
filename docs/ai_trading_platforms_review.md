# Review of AI trading products, exchanges and open-source AI frameworks

Reviewed 2026-10-09. This is a reproducible engineering review, not an endorsement of vendor performance claims. No vendor's marketing claims are treated as evidence of profitability.

## 1. Binance: trading infrastructure and agent tools

Official references:
- AI trading overview: https://academy.binance.com/en/articles/how-to-use-ai-for-crypto-trading
- Trading bots: https://www.binance.com/en/trading-bots
- AI Agent Skills: https://www.binance.com/en/academy/articles/binance-ai-agent-skills-how-to-install-and-use-them
- Agent OS announcement: https://www.prnewswire.com/news-releases/binance-introduces-agent-os-to-connect-ai-applications-to-financial-infrastructure-302856306.html

What is publicly documented:
- Existing bot families include spot/futures grid, arbitrage/funding capture, rebalancing, DCA/auto-invest and execution splitting such as TWAP.
- Agent interfaces can expose market data, order books, candles, wallet/token analytics and, when explicitly authorized, order management.
- Agent OS is an access/execution layer for AI applications. It does not disclose Binance's proprietary market-making or institutional alpha strategies.
- Exchange infrastructure and an AI agent are not the same thing as a proven profitable signal.

Project use:
- Add exchange microstructure features (spread, top-of-book imbalance, depth imbalance, trade-flow imbalance) to research features only when the relevant historical data is actually available.
- Compare trend, grid/range, rebalancing, funding-neutral and execution-slicing baselines separately. Do not treat grid or DCA as universally profitable.
- Keep order execution separate from signal generation; this research branch cannot place orders.

## 2. Freqtrade / FreqAI: open-source adaptive ML

Official references:
- https://docs.freqtrade.io/en/2026.5/freqai-running/
- https://docs.freqtrade.io/en/2026.5/freqai-reinforcement-learning/
- https://docs.freqtrade.io/en/2026.5/

Useful documented engineering patterns:
- Periodic rolling retraining and chronological backtesting that simulates retraining.
- Multi-timeframe and cross-pair features, shifted historical candles, explicit labels, prediction-history storage and stale-model expiry.
- Outlier handling, data normalization and model lifecycle management.
- Reinforcement learning is optional and computationally heavier; its reward design can be exploited by the model and its simplified training environment may not match real execution.

Project use:
- Prefer the light-weight walk-forward retraining/evaluation pattern before deep learning or reinforcement learning.
- Add a model-age/staleness check, and persist predictions with timestamps and model identifiers.
- Treat multi-timeframe/cross-asset features as hypotheses, with all features strictly lagged to the time they would have been known.
- Do not install the heavy FreqAI/RL stack on the user's Android Termux phone; use GitHub-hosted research runners for heavy experiments.

## 3. Pionex and commercial AI/bot platforms

Official reference:
- Pionex grid bot reference: https://www.pionex.com/blog/pionex-grid-bot/
- Cryptohopper strategy editor: https://docs.cryptohopper.com/docs/marketplace/what-are-strategies

Publicly described functionality includes AI-assisted grid parameter suggestions and rule/indicator-based strategy builders. Public product descriptions do not establish net profitability after fees, spread, slippage, funding and adverse selection. Third-party strategy marketplace claims need independent trade-level data to be verified.

Project use:
- Include a fixed grid/range baseline only in a regime-aware comparison: range strategies should be tested separately from trend strategies.
- Do not copy opaque paid strategy signals or scrape private accounts. Reproduce the disclosed rule family, then test it on untouched data.

## 4. Research policy and next experiments

Priority order:
1. Run the fixed-rule real-data tournament across BTC, ETH, SOL, BNB and XRP with cost stress.
2. Finish the lagged FRED cross-market feature experiment (broad USD, S&P 500, gold, WTI oil, VIX).
3. Add a regime label (trend/range/high-volatility) and compare each strategy family within each regime without tuning on the holdout.
4. Add a light rolling/expanding-window model benchmark, with a naive baseline and cost-aware trading threshold. Persist each prediction and model timestamp.
5. Add exchange microstructure and perp funding features only where genuine historical data and timestamp provenance exist.
6. Add grid, funding-neutral, and TWAP-style execution baselines with realistic turnover/cost assumptions.
7. Use multiple chronological windows, cost stress, drawdown and effective trade count before shadow/paper testing.

Promotion gates remain unchanged:
- Positive net expectancy after realistic costs and, for perpetuals, funding.
- Out-of-sample lift against simple baselines across more than one window and regime.
- Sufficient independent trades and acceptable drawdown.
- Robustness to increased costs and removing the best trade.
- Shadow/paper observation before any consideration of real execution.

No secret exchange strategy has been reverse-engineered or claimed. The project only adopts reproducible, publicly described methods after independent validation. Research mode remains on, live orders remain disabled, and this document changes no runtime or protected services.
