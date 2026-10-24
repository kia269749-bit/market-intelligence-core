# External Trading-Skill Audit and Integration Map

Date: 2026-10-24

## Decision

Do not install or copy entire skill packs into the signal bot. These repositories are primarily agent instructions, prompts, workflow manifests, and sometimes helper scripts; they are not drop-in Termux bot modules. Reuse the verifiable research methods in the Python research pipeline, keep exchange/data adapters separate, and reject methods whose dependencies or market assumptions do not match the project.

Project constraints retained:
- Futures research basis; Hyperliquid is the current read-only market-data source, while LBank Futures remains the centralized cost model.
- Central published-default model: taker fee 6 bps + spread 2 bps + slippage 3 bps + impact 1 bp per side = 24 bps / 0.24% round trip. Account-specific fees are not verified.
- Research-only, `live_orders=false`; no private-account or order endpoints.
- The separate 20% round-trip sensitivity is a comparison scenario only. It does not overwrite the central execution assumptions.

## Repository-by-repository findings

### 1. DaviddTech/ai-trading-agent

Source: https://github.com/DaviddTech/ai-trading-agent

- Design: research-desk prompts for strategy hypothesis creation, Pine Script generation, multi-symbol/timeframe backtests, parameter optimization, risk review, and strategy version comparison.
- Strategy families named in the skill pack: mean reversion, trend following, volatility/breakout, multi-timeframe, liquidity-sweep/pattern studies, position sizing and drawdown control.
- External dependency: Trader Dev MCP at `mcp.trader.dev`; the skill files do not perform the heavy backtest themselves. Some MCP operations require an account/authentication. Any reported example performance is illustrative and not evidence for this project.
- Reuse: baseline-first experiments, one-variable-at-a-time changes, no-lookahead/no-repaint audit, multi-symbol and multi-timeframe robustness, report outliers and drawdown.
- Do not reuse directly: remote strategy mutation/promotion, live-alert management, or Pine/TradingView-only backtests as evidence for LBank Futures.

### 2. himself65/finance-skills: tradingview-mcp

Source: https://github.com/himself65/finance-skills

- Design: headless TradingView public-scanner/Yahoo Finance MCP tools for quotes, technical summaries, multi-timeframe analysis, scans and some backtests; read-only by description.
- Setup/dependency notes: documented use of `uv` / `uvx` and Python 3.10-3.13; most market-data calls need no API key, while optional news enrichment may need a token. Termux compatibility has not been proven by this audit.
- Reuse: timestamp, exchange, symbol, currency and data-freshness checks; treat returned errors as errors; document period, interval, costs, sample count and benchmark for any backtest.
- Do not use as the canonical price/cost source: scanner symbol conventions and Yahoo-backed history may not match LBank SwapU contracts or contract economics.

### 3. ljsd666/openclaw-tradingview-quant

Source: https://github.com/ljsd666/openclaw-tradingview-quant

- Design: workflow/reference skill for TradingView-shaped market analysis, screening, technical patterns, risk management and event-driven analysis.
- Dependency: the repository is an agent skill/workflow framework, not a verified native Termux exchange adapter; its TradingView API/MCP path must be independently verified.
- Reuse: structured hypotheses, source provenance, multi-timeframe context, risk checklists and explicit treatment of untrusted news text.
- Do not import its stock-oriented scoring or undocumented API assumptions into the futures model without tests.

### 4. tradermonty/claude-trading-skills

Source: https://github.com/tradermonty/claude-trading-skills

- Index audit: 74 skill IDs were present in `skills-index.yaml` at the time of review.
- High-value research methods: `backtest-expert`, `signal-postmortem`, `crypto-regime-analyzer`, `edge-pipeline-orchestrator`, `residual-edge-analyzer`, `manifoldbt-backtester`, `trader-memory-core`, and `weekly-performance-digest`.
- Cost/dependency notes: several local calculation skills are keyless; other workflows require external data/broker providers such as FMP or Alpaca. The `crypto-regime-analyzer` documents public CoinGecko and Binance funding sources without API keys, but its thresholds are heuristic and it explicitly lacks a pinned historical dataset and reproducible walk-forward return validation.
- Reuse: explicit hypothesis/rules, conservative fees/slippage, parameter plateaus, year/regime breakdown, walk-forward OOS, outcome postmortems, net economics, and fail-closed handling of missing evidence.
- Do not assume every skill's `production` label means its unit tests, financial logic, data provenance, security or empirical edge have been verified; the index marks many of those dimensions `not_verified`.

### 5. agiprolabs/claude-trading-skills

Source: https://github.com/agiprolabs/claude-trading-skills

- Repository advertises 68 skills in its current index/README family; external directory mirrors can show different counts, so the checked-out repository index is authoritative.
- High-value methods: walk-forward/purged validation and embargo, OHLCV gap/anomaly handling, feature engineering, market microstructure, slippage modeling, portfolio analytics, trade journal/postmortem, strategy specification and bounded risk sizing.
- Dependencies/costs: local Python backtesting can be keyless, but individual data skills may use CoinGecko, Binance, Birdeye, Helius or other APIs; some have plan-gated or paid tiers. DEX execution, copy trading and transaction-signing skills are out of scope and must not be wired into this research-only project.
- Reuse: methodology and isolated deterministic calculations only after license/dependency/code review. Do not copy API keys, provider-specific assumptions, Solana/DEX execution code or equity-only rules into LBank Futures.

## What has been integrated into the Project60 research path

The companion code change adds:
- Cost repricing on the same OOS prediction set under the central model, 1.5x and 2x friction, plus a separate 20% round-trip sensitivity.
- A fail-closed research quality gate with distinct `REJECT`, `INSUFFICIENT_EVIDENCE`, and `PASS` outcomes.
- Majority-class accuracy lift and balanced accuracy in the OOS integrity report.
- Timestamp-unit handling for Unix seconds versus milliseconds, and no synthetic adjacency across missing timestamps.
- Explicit requirements for preregistration, verified data provenance, parameter robustness, multiple-testing control, baseline uncertainty intervals and regime stability before a research PASS.

The new gate is diagnostic only: it does not alter live signal tiers, central cost settings, exchange adapters or order behavior.

## Strategy families to evaluate, not assume profitable

1. Slow trend following / Donchian breakout (4h/daily) as a low-turnover candidate.
2. Volatility-normalized trend and breakout variants, with fixed rules and ATR-aware risk.
3. Mean reversion only in explicitly defined range regimes, with trend-regime exclusion.
4. Order-book / trade-imbalance / funding context as a feature or filter only after data provenance and historical availability are verified.
5. Signal postmortem and outcome memory to attribute results by asset, regime, source and horizon.

Every candidate must be compared with a majority/directional baseline, buy-and-hold where appropriate, and a matched-turnover random baseline. Use chronological walk-forward evaluation with horizon-sized embargo or dependence-aware inference; do not tune on the final holdout.

## Execution-cost table

| Scenario | Round-trip cost | Meaning |
|---|---:|---|
| Central LBank Futures model | 0.24% | Published-default model, not account-verified |
| 1.5x friction | 0.36% | Conservative stress test |
| 2x friction | 0.48% | Severe but plausible sensitivity |
| User high-cost comparison | 20.00% | Separate diagnostic comparison only, not an execution estimate |

Cost sensitivity is calculated from identical predictions so a changed result is attributable to the cost assumption, not a different model. No scenario is evidence of actual fills; historical spread, slippage, impact and contract-specific costs still need empirical validation.

## Evidence boundary

Passing unit tests proves software behavior, not predictive power. A strategy can be called a research candidate only after it clears preregistered OOS sample, baseline-lift, net expectancy, profit-factor, drawdown, cost-stress, regime/year stability and multiple-testing gates. No result is labelled profitable when the required historical Futures dataset or required evidence is missing.
