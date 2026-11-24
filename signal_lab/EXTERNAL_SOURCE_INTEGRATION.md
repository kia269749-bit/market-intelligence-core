# External source integration policy (Project60)

## Why this file exists
This is the source-integration track, separate from the frozen Signal Lab v1 experiment registry. It records upstream capabilities and vendor-published evidence. It does **not** add or mutate candidates in `signal_lab/TRIALS.json` after lock.

## Five-step reuse workflow
1. **Source provenance:** verify the official upstream repository/docs, version/commit, license, and maintainer identity. Exclude forks unless upstream is unavailable and the fork is explicitly justified.
2. **Vendor evidence reuse:** record the tests/benchmarks already published by the maintainer or paper, what they actually measure, market/data horizon, and stated limitations. Do not rerun training, vendor benchmark suites, or broad backtests merely to reproduce them.
3. **Read-only extraction:** isolate only the reusable analysis, indicator, forecast, data, risk, or agent-report component. Exclude all order placement, wallet signing, broker execution, credential generation, and self-modification paths.
4. **Project adapter:** normalize each result into the Project60 signal contract: source_id, symbol/chain, timeframe, direction/bias, forecast_horizon, confidence/uncertainty, evidence, as_of_utc, data_timestamp, freshness, and status. Preserve raw vendor output and source version.
5. **Online brain use:** query the adapters against current public market data, combine independent outputs with timestamps and provenance, and emit a signal only when data is fresh and risk gates pass. Missing, stale, contradictory, or inaccessible sources abstain; they do not silently fall back. This is research/paper-only, never order execution.

## Rules
- Project60 round-trip cost remains 0.12% for applicable simulated signal economics.
- No real orders, testnet orders, broker keys, wallet private keys, or exchange execution endpoints.
- No edits to telegram-bot, Forward Test v2, or protected Termux services.
- Do not install heavy engines into Android Termux. Use cloud CI/runner for model inference or heavy engines when compatible.
- Do not import code with incompatible or unreviewed licenses. A documented architecture reference is not a code dependency.
- A published benchmark is evidence only for its stated task. Forecast accuracy, agent reasoning, backtest returns, and execution-engine correctness are different claims.
- New sources discovered after the existing TRIALS lock go into this catalog. They require a new separately frozen source batch before any strategy-specific comparison; do not silently append them to the locked experiment.

## Initial source routing
- First read-only live integration: GMGN public demo key for market/token/wallet data only. Do not invoke swap/order skills.
- Forecasting integration: Kronos pretrained inference only when model host and cloud runtime are available. No retraining.
- Social signal integration: xAI X Search through a restricted read-only tool allowlist; requires an xAI API key and has usage-based charges.
- Multi-agent analysis: TradingAgents analyst/debate/risk reports only; no simulated exchange or broker executor.
- Market data and agent tools: OpenBB as a data/MCP candidate; provider-specific authentication may apply.
- Strategy logic: Freqtrade strategy repository and selected Jesse examples, subject to each strategy's license and existing published evidence.
- Infrastructure references: Qlib, FinRL-X, Hummingbot, NautilusTrader. Reuse interfaces and architecture, not whole trading bots.
- Watchlist only: OpenAlice (experimental and execution-capable); OctoBot (GPL-3.0-or-later and execution-capable).

## Phase 0 BTC screen record (2026-11-24)
The existing script tested only the fixed EMA20/EMA50 + RSI14 + 20-bar breakout candidate. It did not run Kronos, GMGN, Freqtrade, TradingAgents, or any other catalog source. The sealed holdout was consumed once by that script. Summary is in `signal_lab/reports/phase0_btc_summary.json`; the detailed runner report commit push failed non-fast-forward, so no claim is made that the full report artifact was stored by that run.
