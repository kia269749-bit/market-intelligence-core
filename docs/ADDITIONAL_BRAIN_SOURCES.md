# Additional Brain Source Integration Plan

Status: source admission and interface specification only. This document does not claim that the six sources are already executable or that their outputs have been validated in Project60.

## Shared integration contract

- Keep the Project60 runtime research-only: `live_orders=False`. These integrations may inform live market analysis and shadow signals, never place orders.
- Preserve the locked `EDGE_SEARCH_v1` / PR #131 trial registry and all Forward Test files.
- New economic decisions use the single operational assumption of **0.12% round-trip LBank Taker cost**. Do not add separate spread, slippage, impact, 0.15%, or 0.45% assumptions to this new path.
- All components must consume a common, timestamped market snapshot and return structured evidence with source/version, event time, input window, output, confidence/uncertainty, and data-quality status.
- No component gets a direct vote merely because it is installed. The brain's selector weighs only validated, causal, non-stale outputs. Missing or invalid data means unavailable, not a fabricated neutral observation.
- Do not import whole external applications or add their dependency trees blindly. Prefer small native Python adapters behind stable interfaces; record upstream attribution and license.

## Source register

| Source | Upstream | License / type | Intended brain role | Admission state |
|---|---|---|---|---|
| HyperGrok | https://github.com/galleonlabs/hypergrok-trading-desk | MIT; agent roles, skills and read-only Hyperliquid tools | Market/research/risk/reviewer role patterns; reuse only read-only public-data schemas, timestamping, provenance and review workflow | Candidate verified from upstream README; no code imported |
| TradeMemory | https://github.com/mnemox-ai/tradememory-protocol | MIT; local-first trade memory and MCP server | Decision journal, similar-loss recall, outcome memory and pre-signal risk reminders | Candidate verified from upstream README; implement native Project60 storage/API, not broker proxy |
| Forven | https://github.com/judder659/Forven | AGPL-3.0-or-later; self-hosted multi-agent quant research/paper workspace | Strategy/quant/risk agent workflow, robustness concepts and paper-outcome lifecycle | Architecture candidate only; AGPL requires separate compatibility/legal review before copying or linking code |
| Circuit Framework | https://github.com/EthanXiang777/circuit-framework | README declares Apache-2.0; crypto multi-agent research and deterministic risk gate; fork of TradingAgents | Shared immutable market snapshot, specialist debate, structured LONG/SHORT/NO_TRADE proposal and independent deterministic risk gate | Provisional repository identity; verify upstream lineage, exact license file and code before reuse |
| Funding | Existing Project60 funding-event feed / Hyperliquid public funding history | Market-data feature, not a standalone code repository | Derivatives pressure/context; latest settled event only, timestamp <= candle close; exact close included, +1 ms excluded | Data contract retained; no signal weight until feed coverage and causal alignment are verified |
| Kronos | https://github.com/shiyu-coder/Kronos | MIT; pretrained financial-candlestick time-series foundation model | Optional OHLCV sequence forecast / representation evidence alongside existing indicators and forecasts | Model candidate; no weight or runtime activation until model/data compatibility, resource cost, causal inference and out-of-sample behavior are verified |

## Adapter boundaries

### HyperGrok
Extract role boundaries and read-only public market-data patterns only. HyperGrok explicitly says it does not bundle a trading signal or strategy. Its execution trader, wallet, order, mandate, testnet and mainnet flows are out of scope for Project60.

### TradeMemory
Implement a Project60-native append-only decision/outcome journal and analogous-loss retrieval. Store the original thesis, source evidence IDs, regime, entry reference, stop/targets, timestamp, and eventual gross/net outcome. The memory layer must not submit or proxy orders. Treat the upstream project's empirical performance claims as unverified.

### Forven
Use the research-agent separation and paper-evidence lifecycle as architectural references only until AGPL compatibility is explicitly resolved. Do not import its UI, backend, daemon, exchange execution, or dependency graph. Its own README states that live profitability has not been established.

### Circuit
Use one immutable snapshot for all specialists, structured proposals, and a deterministic independent risk gate. Preserve NO_TRADE as a first-class outcome. No LLM or specialist may override the gate. Verify this exact fork and its license before source reuse.

### Funding
Use only observed, settled funding events with event timestamps no later than the candle close being evaluated. No averaging, future leakage, invented zero observations, or weight updates from missing samples. Missing funding stays explicitly unavailable in the evidence record; if the model input contract requires a neutral fill, preserve a separate missingness flag.

### Kronos
Keep as an optional forecast expert, not the decision-maker. Start with a small model variant only after checking its runtime dependencies, model weights, Android/Termux feasibility, inference latency and memory use. Require strict closed-candle inputs and timestamped forecast horizons. Its forecast must pass the same independent signal and economic gates as every other source. Do not modify or reopen PR #131's historical Kronos trial records.

## Required acceptance checks before enabling any source

1. License/provenance and exact upstream revision recorded.
2. Adapter contract and schema tests pass without network access.
3. Timestamp/closed-candle causality tests pass, including boundary tests.
4. Missing, stale, malformed and partial inputs fail closed and remain visible.
5. No order-capable code path, credentials, or protected service dependency is introduced.
6. Runtime/dependency footprint is compatible with the target environment.
7. Outcomes are journaled and measured after the single 0.12% round-trip cost assumption.
8. The brain can abstain; no source is promoted solely from a claimed win rate or upstream benchmark.

## Current status

This change registers the six requested sources and defines their integration boundaries. It does **not** yet mean HyperGrok, TradeMemory, Forven, Circuit, Funding or Kronos is active in live inference. Each adapter and its tests must be implemented and verified before the brain may consume its output.
