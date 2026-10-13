# Global trading research: what is worth combining (2026-10-10)

This note converts public research and open-source trading-system designs into testable hypotheses for Market Intelligence Core. It does not endorse vendor performance claims and does not authorize live trading.

## Findings and source review

### 1. Cost-aware multi-asset trend following is a better next hypothesis than adding more standalone indicators

- Public implementation/research reference: https://github.com/PeterLP123/systematic-crypto-research
- Its documented trend-following candidate uses volatility-normalized moving-average signals across BTC, ETH, BNB and ADA, with covariance-aware constrained portfolio sizing and walk-forward selection.
- The same repository's BTC-dominance mean-reversion candidate failed its holdout and has very few entries. The authors preserve the failure rather than retune it. The project also explicitly notes BTC concentration and limited sample length in its trend results.
- Decision: borrow the research discipline and test the trend/volatility/risk-sizing architecture, not its reported return numbers. Do not adopt BTC-dominance mean reversion without a new independent test.

### 2. Add a separate market-neutral funding/basis hypothesis, not another directional vote

- Hummingbot's public spot-perpetual arbitrage design pairs spot and perpetual legs when their spread diverges, then closes when it converges: https://hummingbot.org/strategies/v1-strategies/spot-perpetual-arbitrage/
- Hummingbot describes the strategy as a two-leg spot/perpetual operation; a profitable result must still include both legs' fees, spread, slippage, funding, basis risk, and fill risk.
- Decision: prototype as a separate strategy family only when timestamp-aligned historical spot prices, perp prices, funding payments and realistic two-leg execution costs are available. Do not mix it into the directional score, and do not infer profitability from current funding alone.

### 3. Borrow adaptive walk-forward engineering, not a heavy AI stack

- FreqAI documents rolling training/backtesting windows and prediction history: https://docs.freqtrade.io/en/2026.5/freqai-running/
- Decision: prefer an expanding/rolling walk-forward benchmark with timestamped predictions, frozen model identifiers, stale-model checks and a naive baseline. Keep heavy model training on GitHub-hosted runners, not Android Termux. Reinforcement learning is not a first step.

### 4. Market-making, grids, and execution algorithms are separate economic strategies

- Hummingbot's public framework documents market-making, grid, TWAP, arbitrage and spot-perpetual components: https://github.com/hummingbot/hummingbot
- Decision: compare grid/range behavior only in range regimes; compare trend-following only in trend regimes. TWAP is an execution method, not a predictive alpha signal. Market making needs quote/fill/order-book replay data and cannot be fairly judged from daily OHLC alone.

### 5. Validation warnings are part of the strategy, not paperwork

- 2026 crypto research on overfitting and independent validation:
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7085378
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7350238
  - https://doi.org/10.2139/ssrn.6508779
- These works report that large strategy searches, full-sample selection, missing costs, and accuracy-only metrics can fail to transfer to unseen data. They are research papers, not guarantees, and their claims require independent scrutiny.
- Decision: no promotion based on a single positive holdout. Preserve failed variants; use multiple chronological windows, cost stress, drawdown, trade count, ablation, and shadow/paper observation.

## Current combined-strategy experiment: exploratory results, not approval

Workflow: https://github.com/kia269749-bit/market-intelligence-core/actions/runs/37989157851
Artifacts: per-asset `combined-strategy-cost-<SYMBOL>` artifacts in that workflow.
The experiment evaluated fixed-rule blends and component baselines on daily Binance OHLC, 2,500 bars per asset, $500 starting capital, next-open execution, a chronological 70/30 development/holdout split, and round-trip cost scenarios 0.20%, 0.25%, and 0.35%.

At the 0.35% modeled cost, the regime-adaptive blend's reported holdout net PnL / maximum drawdown was:
- BTC: +$66.69 / 30.73%
- ETH: +$370.50 / 25.26%
- SOL: +$82.66 / 28.23%
- BNB: +$460.20 / 28.35%
- XRP: +$35.98 / 63.67%

The weighted-consensus blend was +$50.09 BTC, +$47.35 ETH, +$12.77 SOL, +$310.39 BNB, and +$239.84 XRP; respective maximum drawdowns were 32.61%, 36.63%, 37.20%, 34.92%, and 53.38%.

**Critical qualification:** these results are exploratory. The blend was designed and evaluated within this research cycle, so this same holdout must not be treated as untouched evidence for strategy promotion. The large drawdowns, especially XRP, are material. Daily OHLC does not reconstruct historical spread/slippage, funding, partial fills, outages or taxes. The 0.25% case is a 0.20% fee baseline plus a 0.05% assumed combined spread/slippage; 0.35% is a stress assumption, not an exchange fee.

## Next experiments, in priority order

1. Freeze the two blend specifications and all parameters. Do not tune them on the current holdout again.
2. Add a multi-asset portfolio test with volatility-normalized sizing and a hard per-asset / portfolio exposure cap. Compare equal-weight, inverse-volatility and covariance-constrained sizing on synchronized returns. Use next-open execution and realistic turnover costs.
3. Run multiple rolling/expanding walk-forward windows, reporting each window separately and combined. Include cost stress and remove-the-best-trade sensitivity.
4. Only after adequate independent evidence, shadow/paper the frozen candidate and compare predicted fills with actual executable prices.
5. Build funding/basis-neutral research separately once timestamp-aligned historical spot/perp/funding data is available.
6. Integrate Project60 order-book/trade-flow/OI/funding features only on matching timestamps. Missing or stale data must reduce confidence or block the relevant feature, not be silently imputed.
7. Keep FOMO leader/follower evidence separate until actual timestamped wallet/trade events and reliable outcomes exist; do not substitute social mentions for verified fills.

## Non-negotiable safety and promotion gates

- `research_only=true`, `live_orders=false`, `trade_ready=false`.
- Do not weaken existing profitability gates to force signals.
- Require net expectancy after fees and, for perpetuals, funding; positive OOS lift against simple baselines across multiple windows; sufficient independent trades; tolerable drawdown; robustness to higher costs and removal of the best trade; then shadow/paper validation.
- No live order execution, no edits to protected legacy Termux services, and no merge to main as part of this research note.
