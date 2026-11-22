# Project60 Brain Source Audit and Integration Map
Date: 2026-11-22
Branch: feat/brain-orchestration-20261122
Scope: known candidate repositories and agent systems collected in Project60 research. This is not a claim that every repository on GitHub or every Grok bot has been discovered.

## Executive finding
No source is admitted as profitable merely because it has a large strategy/indicator count, passing unit tests, or a published backtest. Profitability status is **UNPROVEN** until the same frozen evaluation harness measures out-of-sample net expectancy after the Project60 0.12% round-trip cost, compares Buy & Hold and random/opposite controls, reports sample size and uncertainty, and passes across assets/regimes.

## Verified technical inventories
| Source | Upstream inventory | License/status | Project60 integration state |
|---|---:|---|---|
| PyneCore Strategies | 449 strategies, 471 indicators, 85 Pine libraries | MIT repository; PyneCore runtime required | Candidate corpus only; no bulk strategy runtime or economic evaluation |
| ta_patterns | 300 detectors: 106 candlestick + 194 chart patterns | MIT, NumPy-only core | Adapter added; dynamic per-pattern IDs per timeframe when patterns fire; not yet tested on Project60 market history |
| pandas-ta-classic | 224 indicator/utilities + 62 native candlestick patterns | MIT | Existing indicator brain computes package inventory; only explicitly mapped causal features vote |
| freqtrade/technical | Collected/custom indicators and resampling helpers | GPL-3.0 | Reference/adapter candidate; license review needed before copying |
| TA-Lib | 200+ indicators and candle pattern functions | BSD-2-Clause wrapper/native library | Optional; native Android build not yet validated |
| Freqtrade strategies | Community strategy repository | GPL-3.0 | Generic Freqtrade adapter exists; no bulk strategy import or profitability claim |

Important: 351 was the previous Project60 **software test count**, not the count of trading strategies. The verified counts above come from upstream repository documentation and still need reproducible local inventory extraction.

## Agent / research source register
| Source | What is reusable | What is not admitted yet |
|---|---|---|
| HyperGrok | Seven role boundaries; six public read-only Hyperliquid data tools; provenance and risk/review workflow | No bundled strategy or signal; execution/wallet/order flows excluded |
| HyperData Terminal | Read-only order-flow/market-data adapter for CVD/OFI with venue health and coverage gates | Adapter contract is wired; feed payload/runtime connection remains external and optional |
| Grok bot directory | hft.md lists 235 public bots across research, paper, approval and autonomous categories | Directory metadata only; prompts/source implementations and actual performance not independently audited bot-by-bot |
| TradeMemory | Local decision/outcome journal, recall, risk reminders and tamper-evident audit concepts | Its own empirical evidence is limited/regime-dependent; adapter is payload-only, not connected |
| Circuit Framework | Shared immutable crypto snapshot, specialist debate and deterministic risk gate; Apache-2.0 claim | Fork lineage/license and code need final verification; use architecture first |
| TradingAgents | Multi-agent analyst/research debate architecture | LLM dependency/cost and no direct proof of net trading edge |
| Forven | Research/quant/risk separation, hypothesis gauntlet and paper evidence lifecycle | AGPL-3.0-or-later; architecture reference only until compatibility decision |
| CryptoIntel-MCP | OFI, OBI, microprice, VPIN, orderbook and anomaly research | Small upstream footprint; ML/sentiment claims and dependency/security review pending; no blind execution-agent import |
| Hummingbot | Market data/connectors and strategy concepts | Exchange execution-capable framework; extract research-only strategy logic only after code review |
| Qlib | Feature/model/backtest research infrastructure | Large dependency footprint; not a ready-made profitable crypto specialist |
| RD-Agent | Automated hypothesis and model research workflows | Heavy research agent; generated hypotheses require independent validation |
| Kronos | Candlestick time-series forecasting model | Model weights/inference runtime, latency, memory and Termux compatibility not verified; forecast-only candidate |
| AI Fund | 45 role/persona agents and shared tools according to upstream README | Exchange/order-capable tools; do not import execution connectors; persona count is not independent evidence |
| autoresearch-crypto | 11 strategy families, regime classification, multi-timeframe and evolutionary research | Has live order paths and different fee assumptions; extract offline research logic only after review |
| Vibe-Trading | Research replay, backtesting, agent orchestration and source-traceability concepts | Security review required; do not execute/import blindly |
| OpenBB | Timestamped macro-data provider abstraction | Data availability and provider/API requirements must be explicit |
| PyneCore | Pine-compatible bar-by-bar runtime and strategy compilation | Strategy source files are executable code; require static review, isolation and exact timeframe/data compatibility |

## Current Project60 runtime tree
```text
Market Intelligence Core
└── Shared timestamped MarketSnapshot (symbol + closed OHLCV + context)
    ├── Technical family
    │   ├── pandas-ta-classic indicator specialists (15m / 1h / 4h / 1d)
    │   ├── 24 native OHLCV strategy specialists (6 strategies × 4 timeframes)
    │   └── ta_patterns dynamic specialists (300 pattern IDs × 4 timeframes when fired)
    ├── Order-flow family
    │   ├── Hyperliquid L2 / OBI / microprice
    │   ├── Project60 orderbook imbalance
    │   └── Project60 executed-trade flow
    ├── Derivatives family
    │   ├── settled funding event (causal timestamp gate)
    │   └── open-interest delta (requires valid repeated observation)
    ├── Forecast family
    │   └── Kronos / Qlib callable interfaces (runtime not admitted)
    ├── Strategy family
    │   ├── Freqtrade adapter (reviewed strategy instance required)
    │   ├── PyneCore callable interface (bulk corpus not loaded)
    │   └── Hummingbot / TradingAgents / RD-Agent (pending adapters)
    ├── Macro family
    │   └── OpenBB timestamped context
    ├── Memory family
    │   ├── Project60 append-only OutcomeStore
    │   └── TradeMemory payload bridge (not connected)
    └── Central arbiter
        ├── freshness + closed-candle validation
        ├── family de-correlation / minimum independent families
        ├── per-brain sample-shrunk outcome weighting
        ├── 0.12% RT expectancy check when payoff fields exist
        └── LONG / SHORT / NO_TRADE
            ├── per-specialist signal journal
            ├── per-specialist resolved outcome history
            └── research-only Telegram export (not yet connected)
```

## Timeframe coverage and gaps
| Timeframe | Current native strategy / technical path | Pattern corpus adapter |
|---|---|---|
| 15m | Yes | Added |
| 1h | Yes | Added |
| 4h | Yes | Added |
| 1d | Yes | Added |
| 1m / 5m / 30m / 2h / 6h / 8h / 12h | Not yet in these native technical adapters | Not yet enabled |

PyneCore corpus includes scripts that request nonstandard timeframes (including 25m, 30m, 2h, 6h, 8h, 12h and monthly). They cannot be safely assumed to work on the four current frames. Each strategy needs declared required timeframes and causal higher-timeframe joins.

## Profitability acceptance contract
1. Frozen source revision, rule, parameters, assets, timeframe and data window.
2. Only completed bars and information available at the decision timestamp.
3. Next-bar execution model; no same-candle lookahead or optimistic TP/SL ordering.
4. Current Project60 round-trip cost: 0.12%.
5. Net expectancy, win rate, payoff ratio, trade count, max drawdown, turnover and uncertainty.
6. Chronological train/validation/untouched test or walk-forward OOS; no tuning on final holdout.
7. Buy & Hold, random-entry and opposite-direction controls.
8. Per-asset, per-timeframe and per-regime results; correlated variants not counted as independent samples.
9. Verdict: POSITIVE OOS / NEGATIVE / INSUFFICIENT EVIDENCE. No forced winner.

## Validation status at this commit
- Prior known CI: 351 tests passed on commit 13cd8f9 (before the latest TradeMemory and ta_patterns changes).
- TradeMemory adapter tests were included in CI and passed. The ta_patterns tests were converted to unittest after that run and have **not yet been executed**; run them locally before treating the adapter as test-verified.
- No new GitHub workflow was triggered. Broad legacy research workflows are deliberately not retriggered because a previous temporary PR unexpectedly started economic workflows.
- Termux cannot be controlled from this chat. Local Android/Python validation remains pending until the user runs the supplied read-only test commands and shares output.
- No live orders, testnet, exchange credentials, protected Telegram services, Forward Test files, PR #131, or historical registry were changed.


## 2026-11-22 integration delta

The expanded external-source catalog is maintained in
[EXTERNAL_SOURCE_CATALOG_2026-11-22.md](EXTERNAL_SOURCE_CATALOG_2026-11-22.md).
It separates directional specialists from data providers, research intake,
validation engines and cloud-agent runtimes.

Implemented on this branch:

- Specialist source registry: 50 source-level entries. HyperData is one
  dynamic order-flow source; its timeframe-specific proposals remain in the
  existing orderflow family.
- HyperData Terminal: read-only CVD/OFI adapter wired into evaluate_brains.
  It requires an explicitly supplied MCP payload and checks source timestamp,
  venue status, 95% timeframe coverage, finite values and directional
  consistency. No HyperData process or MCP server is started by Project60.
- xAI Grok: optional Responses API multi-agent research client using built-in
  web_search and x_search only. It returns a research note, not a trading vote.
  It is not called automatically and requires XAI_API_KEY in the runtime.
- purgedcv: optional cloud-validation wrapper for purged walk-forward, PSR and
  DSR on precomputed net-of-cost returns. The dependency is not installed by
  default and the actual upstream package has not yet been run in CI.
- Source catalog: 11 external capability sources, with a public GitHub
  metadata-only update checker. No source code is automatically pulled,
  installed or executed.

Validation on commit 8197969f5ad22d7fcffb7fd69057b4c543a0295e:

- 22 new dependency-free module tests passed.
- 355 existing repository tests passed.
- Market Intelligence CI passed on push and pull_request.
- Live Market Smoke passed, including one real multi-exchange read-only snapshot.
- No legacy economic/backtest workflow was triggered. The only workflows for
  this commit were the two CI runs and Live Market Smoke.
- Grok API, HyperData live feed and purgedcv's real optional runtime were not
  invoked; their adapters were tested with controlled fixtures/mocks.

The GitHub branch is updated. The Android Termux worktree remains at the
previous 8cf7988 snapshot until the user synchronizes it. No local Termux
commands, services, Forward Test files, PR #131 or historical registries were
changed by this GitHub work.
