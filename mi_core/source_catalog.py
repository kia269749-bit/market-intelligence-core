"""Curated external capability catalog for Project60.

This is deliberately separate from SPECIALIST_SOURCES: data providers,
research tools, validators, and agent runtimes are not directional voters.
The updater only reads public GitHub metadata. It never clones, installs,
imports, executes, or modifies upstream code.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ExternalSource:
    source_id: str
    name: str
    role: str
    url: str
    github_repo: str | None
    license: str
    status: str
    reviewed_at: str
    capabilities: tuple[str, ...]
    constraints: tuple[str, ...]
    voting_eligible: bool = False


_REVIEWED = "2026-11-22T09:30:00Z"

SOURCE_CATALOG: tuple[ExternalSource, ...] = (
    ExternalSource(
        "orderflow.order_flow_screener", "Order Flow Tracker", "orderflow_engine",
        "https://github.com/zadescoxp/order-flow-screener",
        "zadescoxp/order-flow-screener", "Apache-2.0", "source_review_required", _REVIEWED,
        ("footprint", "CVD", "absorption", "iceberg", "liquidity_heatmap", "cross_venue_normalization"),
        ("Uses Siebly exchange SDKs; port reviewed calculations rather than importing the UI/feed stack.",
         "No broker or order execution capability is needed."),
    ),
    ExternalSource(
        "market.hyperdata_terminal", "HyperData Terminal", "read_only_market_data",
        "https://github.com/Co-Messi/HyperData-Terminal",
        "Co-Messi/HyperData-Terminal", "Apache-2.0", "mcp_adapter_review_required", _REVIEWED,
        ("whale_positions", "liquidation_heatmap", "CVD", "funding", "open_interest",
         "data_integrity_status", "read_only_mcp"),
        ("Requires Python 3.12+; MCP server is local stdio by default.",
         "Use only read-only methods; never expose paper/order interfaces."),
    ),
    ExternalSource(
        "validation.purgedcv", "purgedcv", "research_validation",
        "https://github.com/eslazarev/purged-cross-validation",
        "eslazarev/purged-cross-validation", "MIT", "optional_cloud_validation_candidate", _REVIEWED,
        ("purging", "embargo", "walk_forward", "combinatorial_purged_cv", "PSR", "DSR", "PBO"),
        ("Optional only; depends on NumPy, pandas, scikit-learn and SciPy.",
         "Cloud validation candidate; do not install by default on Android Termux."),
    ),
    ExternalSource(
        "validation.oos_lab", "OOS Lab", "research_validation",
        "https://github.com/OutOfSampleLab/oos-lab",
        "OutOfSampleLab/oos-lab", "MIT", "secondary_validation_candidate", _REVIEWED,
        ("PSR", "DSR", "PBO", "walk_forward", "multiple_testing_haircut"),
        ("Small upstream project; independently inspect implementation and tests before adoption.",
         "Validation only; never a directional voter."),
    ),
    ExternalSource(
        "research.research_intelligence_platform", "Research Intelligence Platform",
        "research_intake", "https://github.com/zabor-crypto/research-intelligence-platform",
        "zabor-crypto/research-intelligence-platform", "MIT", "offline_hypothesis_pipeline_candidate", _REVIEWED,
        ("paper_and_repo_ingestion", "hypothesis_extraction", "eligibility_scoring", "backtest_handoff"),
        ("Offline mock workflow is available; real LLM providers are optional.",
         "A hypothesis or handoff is not evidence of profitability."),
    ),
    ExternalSource(
        "runtime.sandbase_harness", "SandBase Harness", "agent_runtime",
        "https://github.com/sandbaseai/sandbase-harness",
        "sandbaseai/sandbase-harness", "Apache-2.0", "cloud_runtime_candidate", _REVIEWED,
        ("sandboxed_sessions", "MCP_toolsets", "memory", "approval_policies", "audit_replay"),
        ("Node.js 22+; Docker/Kubernetes are optional runtime backends.",
         "Cloud/self-hosted candidate, not a Termux dependency."),
    ),
    ExternalSource(
        "data.tardis", "Tardis Dev", "historical_market_data",
        "https://github.com/tardis-dev/tardis-node",
        "tardis-dev/tardis-node", "MPL-2.0", "data_provider_terms_review_required", _REVIEWED,
        ("historical_ticks", "L2_order_book_replay", "trades", "funding", "open_interest", "liquidations"),
        ("Node.js client and external data API; verify data entitlements, retention and cost.",
         "No data key or paid plan is assumed to exist."),
    ),
    ExternalSource(
        "data.candlefeed", "CandleFeed", "historical_market_data",
        "https://github.com/candlefeed-ai/candlefeed-python",
        "candlefeed-ai/candlefeed-python", "MIT", "api_key_and_plan_required", _REVIEWED,
        ("OHLCV", "funding", "open_interest", "liquidations", "basis", "options"),
        ("Requires a provider API key; free tier is limited and multi-venue/deep data are paid.",
         "Pandas dependency; no key is embedded or requested by this catalog."),
    ),
    ExternalSource(
        "research.vectorbt", "VectorBT Community", "research_engine",
        "https://github.com/polakowo/vectorbt",
        "polakowo/vectorbt", "Commons-Clause-license-review", "license_review_required", _REVIEWED,
        ("vectorized_backtesting", "parameter_sweeps", "portfolio_metrics", "walk_forward"),
        ("Repository API reports NOASSERTION; README describes Apache 2.0 with Commons Clause.",
         "Do not copy, install or distribute until exact license obligations are reviewed."),
    ),
    ExternalSource(
        "research.edgedepth_mcp", "EdgeDepth Research MCP", "research_validation_data",
        "https://github.com/edgedepthhq/edgedepth-research-mcp",
        "edgedepthhq/edgedepth-research-mcp", "MIT", "external_api_review_required", _REVIEWED,
        ("historical_microstructure_queries", "deterministic_mcp", "evidence_retrieval"),
        ("Requires access to an external research API; verify coverage, pricing and provenance.",
         "Evidence retrieval only; no directional vote."),
    ),
    ExternalSource(
        "agent.xai_grok_multi_agent", "xAI Grok Multi-Agent", "cloud_research_agent",
        "https://docs.x.ai/developers/model-capabilities/text/multi-agent",
        None, "proprietary_api", "beta_api_integration_pending", _REVIEWED,
        ("parallel_research", "web_search", "X_search", "code_execution", "research_synthesis"),
        ("API usage is billed; multi-agent API is beta and model behavior may change.",
         "Use a dedicated read-only MCP allowlist; never expose order, wallet or secret tools.",
         "Requires XAI_API_KEY in the runtime environment; never paste it into chat or commit it."),
    ),
)


def list_external_sources(role: str | None = None) -> list[dict]:
    """Return catalog metadata; external sources are not specialist votes."""
    rows = [item for item in SOURCE_CATALOG if role is None or item.role == role]
    return [asdict(item) for item in rows]


def check_upstream_activity(
    sources: tuple[ExternalSource, ...] | None = None, timeout: float = 5.0
) -> list[dict]:
    """Read public GitHub repo metadata and flag activity since the last review.

    This is a discovery signal, not an update/install mechanism. A changed
    upstream must pass source diff, license, dependency, security and test review.
    """
    report: list[dict] = []
    for item in sources or SOURCE_CATALOG:
        if not item.github_repo:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", item.github_repo):
            report.append({"source_id": item.source_id, "check_status": "invalid_repo"})
            continue
        request = Request(
            f"https://api.github.com/repos/{item.github_repo}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Project60-SourceCatalog/1",
            },
        )
        row = {"source_id": item.source_id, "repo": item.github_repo}
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            updated_at = str(payload.get("updated_at") or "")
            license_info = payload.get("license") or {}
            actual_license = license_info.get("spdx_id") or "NOASSERTION"
            row.update({
                "check_status": "ok",
                "updated_at": updated_at,
                "archived": bool(payload.get("archived", False)),
                "stars": int(payload.get("stargazers_count") or 0),
                "reported_license": actual_license,
                "activity_since_review": bool(updated_at and updated_at > item.reviewed_at),
                "license_matches_catalog": actual_license == item.license,
            })
            if row["archived"] or row["activity_since_review"] or not row["license_matches_catalog"]:
                row["review_required"] = True
            else:
                row["review_required"] = False
        except Exception as exc:
            row.update({"check_status": "unavailable", "error_type": type(exc).__name__})
        report.append(row)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Project60 external source catalog")
    parser.add_argument("--check", action="store_true",
                        help="read public GitHub metadata; never downloads or executes source code")
    parser.add_argument("--role", help="filter by capability role")
    args = parser.parse_args()
    if args.check:
        result = check_upstream_activity()
    else:
        result = list_external_sources(args.role)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
