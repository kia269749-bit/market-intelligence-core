# Project60 Brain Mesh Architecture

## Decision
Project60 is an open-ended, hierarchical mesh of specialist brains, agents, models, indicators, patterns, strategies, data providers, news and risk analysts. There is no arbitrary fixed count limit. Scale is bounded only by compute, data access, licensing, latency, reliability and budget.

## No vendor re-testing
Reuse each source's published validation as evidence. Do not retrain a vendor model, reproduce its benchmark suite, or rerun its full strategy backtest merely to repeat the vendor's work. Preserve upstream version, validation reference, metric, dataset/market, period and limitations. Never generalize vendor validation beyond its original scope.

Integration checks are operational compatibility only: access, output parsing, timestamps, version, rate limits, license and read-only permissions. They are not performance retests.

## Mesh layers
1. Source layer: repositories, APIs, papers, model hubs, agent skills, indicator libraries, strategy collections, market feeds, news and social sources.
2. Specialist brain layer: isolated workers for price action, technical indicators, patterns, volatility, order book, derivatives, on-chain, smart money, news, X/social, macro, sentiment, strategy interpretation, portfolio/risk, data quality and meta-analysis.
3. Domain councils: combine related specialists such as market structure, on-chain, derivatives, social/news, macro, execution-cost and risk.
4. Meta-brain: compares councils, tracks disagreement and missing evidence, prevents duplicate evidence from being counted as independent, and decides whether to publish a research/paper signal or abstain.
5. Signal journal: immutable timestamped outputs and source provenance; never writes orders.

## No fixed brain count
The registry is data-driven. New brains and sources can be registered without code changes when they implement the common contract. Orchestration uses bounded concurrency, queueing, caching, timeouts and priority tiers rather than a hard-coded maximum. A brain may delegate to child brains; the parent remains responsible for provenance and aggregation.

## Common brain output contract
Every worker emits brain_id, brain_version, source_id, source_version, symbol, venue_or_chain, timeframe, as_of_utc, input_data_timestamp_utc, observation, bias, optional forecast_horizon, confidence only when defined by the source, uncertainty, evidence references, vendor_validation_refs, freshness, availability, execution_capability and execution_blocked=true.

Never convert an uncalibrated model score into a probability. Never manufacture confidence for a source that does not provide it.

## Aggregation rules
- Weight by source relevance, evidence scope, recency, provenance quality and independence, not popularity or raw agent count.
- Deduplicate shared upstream models, datasets, copied indicators and reposted news. Ten wrappers around one source are not ten independent votes.
- Keep disagreements visible. Domain councils return consensus and minority views.
- Missing, stale or blocked sources abstain; they do not become neutral votes.
- The meta-brain may abstain when evidence is contradictory, stale, duplicated or too thin.
- Preserve source-level outputs so every aggregate traces to original evidence.
- Separate forecast quality, strategy evidence, market-data correctness, execution simulation and risk compliance.

## Five-stage onboarding for every new source
1. Discover and verify upstream identity, maintenance, version and license.
2. Import vendor-published tests/benchmarks and exact scope. Do not rerun them.
3. Isolate reusable read-only capabilities and block orders, wallet signing, broker writes, credential generation and secret access.
4. Build a thin adapter to the common contract. Verify connectivity, schema, timestamps and permissions only.
5. Register the worker in the mesh; route live public market context to it; aggregate its output with provenance and freshness controls.

New sources enter the mesh registry, not a frozen Signal Lab trial. A separate strategy comparison requires its own predeclared experiment; ordinary source consumption does not.

## Compute and cloud policy
- Prefer cloud/remote inference for large models and multi-agent fan-out; keep Android Termux light.
- Use asynchronous queues, bounded concurrency, caching, batching, timeouts and budget caps.
- Route expensive brains only when their specialist domain is relevant.
- No source receives unrestricted tool access. Each adapter gets an explicit allowlist.
- Paid APIs such as xAI/Grok require per-provider spend limits and no implicit paid-call loops.

## Project safety invariants
- research_only=true; live_orders=false.
- No exchange order endpoints, broker write tools, wallet private keys or signing functions.
- Do not change protected Telegram/Forward Test services through this mesh.
- Existing Signal Lab TRIALS.json remains frozen and unchanged.
- Project60 round-trip cost assumption remains 0.12% for applicable paper-signal economics.

## Initial councils
- Market structure: OHLCV, trend, support/resistance, candle patterns, volatility, technical indicators.
- Derivatives and liquidity: funding, open interest, liquidations, order book and spreads.
- On-chain and smart money: GMGN, wallet behavior, holders, token flows and chain events.
- News and social: Grok/X Search, news feeds, sentiment and event extraction.
- Quant and strategy: Freqtrade, Jesse, Qlib/FinRL-X research components and strategy libraries.
- Forecasting: Kronos and other pretrained time-series models.
- Risk and portfolio: drawdown, concentration, regime, liquidity, correlation and cost overlays.
- Meta-council: evidence independence, disagreement, freshness and final abstention/signal decision.
