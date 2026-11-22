# Project60 External Capability Catalog

Date: 2026-11-22
Branch: feat/brain-orchestration-20261122

## Purpose

This catalog extends the brain's discovery and research capabilities without
inflating the count of directional specialists. Data feeds, research intake,
validation engines and agent runtimes are separate capability classes. They
must not vote LONG/SHORT merely because they are connected.

The executable catalog is `mi_core/source_catalog.py`. It uses only the Python
standard library. Run:

```bash
python -m mi_core.source_catalog
python -m mi_core.source_catalog --check
python -m mi_core.test_source_catalog
```

`--check` performs public, read-only GitHub repository metadata requests. It
reports repository activity since the review date, archived status and license
metadata. It does not clone, download, install, import or execute upstream code,
and it writes no files. Network/API failures are reported as unavailable.

## New sources reviewed

| Source | Role | License / access | Candidate use | Current gate |
|---|---|---|---|---|
| [Order Flow Tracker](https://github.com/zadescoxp/order-flow-screener) | Order-flow analytics | Apache-2.0; Siebly exchange SDKs | Footprint, CVD, absorption, iceberg, liquidity heatmap | Port reviewed calculations; do not import full UI/feed stack |
| [HyperData Terminal](https://github.com/Co-Messi/HyperData-Terminal) | Read-only market data | Apache-2.0; Python 3.12+ | Whale positions, liquidation heatmap, CVD, funding, OI, feed integrity and read-only MCP | Review data schema and isolate read-only MCP tools; local stdio is not a remote cloud endpoint |
| [purgedcv](https://github.com/eslazarev/purged-cross-validation) | Research validation | MIT; NumPy, pandas, scikit-learn, SciPy | Purging, embargo, walk-forward, CPCV, PSR, DSR and PBO | Optional cloud validation; do not add to default Android dependencies |
| [OOS Lab](https://github.com/OutOfSampleLab/oos-lab) | Research validation | MIT; NumPy and SciPy | PSR, DSR, PBO, walk-forward, multiple-testing haircut | Secondary candidate; inspect implementation and test provenance |
| [Research Intelligence Platform](https://github.com/zabor-crypto/research-intelligence-platform) | Research intake | MIT; Python 3.11+, several dependencies | Collect papers/repos, extract and rank hypotheses, export backtest handoffs | Offline mock works; hypotheses are not evidence of edge |
| [SandBase Harness](https://github.com/sandbaseai/sandbase-harness) | Agent runtime | Apache-2.0; Node 22+, optional Docker/Kubernetes | Sandboxed sessions, MCP toolsets, memory, approvals, audit and replay | Cloud/self-hosted candidate; not a Termux install |
| [Tardis](https://github.com/tardis-dev/tardis-node) | Historical market data | MPL-2.0; Node client and external API | Tick replay, L2 reconstruction, trades, funding, OI and liquidations | Verify API access, data license, coverage and cost |
| [CandleFeed](https://github.com/candlefeed-ai/candlefeed-python) | Historical market data | MIT client; provider API key and tier limits | OHLCV, funding, OI, liquidations, basis and options | Optional provider; no API key assumed; multi-venue/deep data are paid |
| [VectorBT Community](https://github.com/polakowo/vectorbt) | Research engine | README states Apache-2.0 with Commons Clause; API reports NOASSERTION | Vectorized backtests and parameter sweeps | License review required before copy, install or distribution |
| [EdgeDepth Research MCP](https://github.com/edgedepthhq/edgedepth-research-mcp) | Research evidence/data | MIT client; external API access | Recorded microstructure queries and deterministic MCP evidence retrieval | Verify API access, coverage, pricing and provenance |
| [xAI Grok Multi-Agent](https://docs.x.ai/developers/model-capabilities/text/multi-agent) | Cloud research agent | Proprietary, billed API; beta | Parallel web/X research, analysis and synthesis | Requires runtime key; allowlist read-only MCP tools only |

## Integration order

1. **Data integrity first:** inspect HyperData's LIVE/PARTIAL/STALE/DRIFT semantics and
   map them into a common source-health contract. Do not turn missing data into zero.
2. **Order-flow feature extraction:** compare Order Flow Tracker formulas against
   existing Project60 OBI/microprice/CVD features. Add only non-duplicated, timestamped
   features; same-family correlated signals must not count as independent families.
3. **Research intake:** use the Research Intelligence Platform's structured
   hypothesis/handoff idea. A candidate is admitted only after source/license review,
   reproducible implementation, and frozen OOS evaluation.
4. **Validation:** evaluate purgedcv first as an optional cloud dependency. Compare it
   against Project60's existing walk-forward and leakage tests before choosing one
   canonical implementation. OOS Lab remains a secondary independent cross-check.
5. **Cloud agents:** Grok can research with web/X and selected remote MCP tools. SandBase
   is a possible sandbox/session/audit runtime. Neither is a trading brain until its
   output is structured, timestamped, source-attributed and independently validated.
6. **Historical data:** Tardis and CandleFeed are provider candidates, not assumed free
   feeds. No credentials, paid plans or data entitlements are assumed.

## Controlled self-update policy

The catalog can detect upstream repository activity. It must never auto-pull,
auto-install, execute arbitrary repository code, or silently change a specialist.
Every upstream update requires:

- exact commit/release pin and source diff;
- license and dependency/security review;
- reproducible tests and Android/cloud compatibility check;
- adapter contract and timestamp/look-ahead tests;
- explicit promotion from candidate to runnable;
- independent OOS evidence before any performance weighting or economic claim.

The existing 49-entry `SPECIALIST_SOURCES` registry remains the directional
specialist registry. These capability sources are intentionally not added to it.
The central brain's family-independence rules remain in force.

## Safety and evaluation policy

- `research_only=True`; `live_orders=False`.
- No exchange order, wallet, account or secret tools are admitted to research agents.
- Grok Remote MCP must use an explicit allowlist of read-only tools. xAI documents
  that omitting the allowlist exposes every tool from the MCP server.
- No provider key is committed or pasted into chat.
- New strategies use the current 0.12% round-trip cost, closed bars, causal timestamps,
  next-bar assumptions and untouched chronological OOS.
- Compare Buy & Hold, random-entry and opposite-direction controls.
- Report sample count, expectancy, payoff, drawdown and uncertainty; allow
  POSITIVE OOS, NEGATIVE or INSUFFICIENT EVIDENCE. No forced winner.
- PR #134 remains Draft/Open/Unmerged; no merge is performed by this catalog.


## Optional Grok research runtime

The optional client is `mi_core/brains/grok_research.py`. It calls the official
xAI Responses API using `grok-4.20-multi-agent` and built-in `web_search` /
`x_search` only. It is not invoked by `evaluate_brains` or `live-all`, does
not produce a `BrainProposal`, and cannot submit orders.

Configure `XAI_API_KEY` in the runtime environment (never in source control),
then call `run_grok_research(prompt)` explicitly. Each request is billed and
the multi-agent API is documented as beta. The report retains returned source
URLs and usage metadata when provided.

No remote MCP servers are attached by default. If added later, the MCP server
must expose a dedicated read-only tool set and the xAI request must explicitly
allowlist only those tools. xAI documents that an omitted/empty allowlist can
expose all tools offered by the MCP server.


## HyperData order-flow adapter status

Project60 now has `mi_core/brains/hyperdata_adapter.py`, which consumes the
documented `get_order_flow(symbol)` payload through
`MarketSnapshot.payload["hyperdata_orderflow"]`. It checks the source timestamp,
venue liveness, per-timeframe window coverage (minimum 95%), finite/ranged OFI
and net delta, and agreement between signal direction and raw values.

The adapter emits separate timeframe IDs but assigns every proposal to the
existing `orderflow` family. Therefore HyperData cannot manufacture extra
independent-family votes against Project60's own order-flow specialists.
Missing, stale, warming-up, malformed, or contradictory data become unavailable
proposals, never zero-filled or invented market signals.

This is an adapter contract, not a running HyperData connection. Project60 does
not start HyperData, launch its MCP server, expose its local API, or install its
dependencies. A caller must explicitly supply the read-only payload. HyperData's
own data-integrity documentation warns that liquidation coverage differs by
venue and that Binance liquidation events are sampled while Hyperliquid
liquidations are partial; liquidation values are not treated as complete census
data. The educational liquidation strategy is not imported.
