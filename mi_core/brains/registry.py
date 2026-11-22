"""Source-to-specialist registry with explicit execution readiness.

Every strategy source gets a stable brain ID and its own outcome history.
A source is not marked runnable until a concrete, read-only adapter exists.
"""
from __future__ import annotations

SPECIALIST_SOURCES = {
    "technical.pandas_ta_classic.15m": {"family": "technical", "source": "pandas-ta-classic", "adapter": "technical_adapter", "status": "runnable"},
    "technical.pandas_ta_classic.1h": {"family": "technical", "source": "pandas-ta-classic", "adapter": "technical_adapter", "status": "runnable"},
    "technical.pandas_ta_classic.4h": {"family": "technical", "source": "pandas-ta-classic", "adapter": "technical_adapter", "status": "runnable"},
    "technical.pandas_ta_classic.1d": {"family": "technical", "source": "pandas-ta-classic", "adapter": "technical_adapter", "status": "runnable"},
    "strategy.pynecore": {"family": "strategy", "source": "theonetrade/pynecore-strategies", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.freqtrade": {"family": "strategy", "source": "freqtrade/freqtrade", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.hummingbot": {"family": "strategy", "source": "hummingbot/hummingbot", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.qlib": {"family": "strategy", "source": "microsoft/qlib", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.rd_agent": {"family": "strategy", "source": "microsoft/RD-Agent", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.tradingagents": {"family": "strategy", "source": "TauricResearch/TradingAgents", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.forven": {"family": "strategy", "source": "judder659/Forven", "adapter": "strategy_runtime", "status": "license_review_required"},
    "market.orderbook_imbalance": {"family": "orderflow", "source": "Project60 normalized L2 orderbook", "adapter": "orderbook_adapter", "status": "runnable_when_feed_present"},
    "market.hypergrok": {"family": "orderflow", "source": "galleonlabs/hypergrok-trading-desk", "adapter": "pending", "status": "adapter_pending"},
    "market.circuit": {"family": "orderflow", "source": "EthanXiang777/circuit-framework", "adapter": "pending", "status": "adapter_pending"},
    "market.cryptointel_mcp": {"family": "orderflow", "source": "Arshad-13/CryptoIntel-MCP", "adapter": "pending", "status": "adapter_pending"},
    "derivatives.hyperliquid_funding": {"family": "derivatives", "source": "Project60 settled FundingEvent", "adapter": "derivatives_adapter", "status": "runnable_when_feed_present"},
    "derivatives.open_interest": {"family": "derivatives", "source": "Project60 normalized OI change + price change", "adapter": "derivatives_adapter", "status": "runnable_when_feed_present"},
    "forecast.kronos": {"family": "forecast", "source": "shiyu-coder/Kronos", "adapter": "pending", "status": "runtime_review_pending"},
    "memory.tradememory": {"family": "memory", "source": "mnemox-ai/tradememory-protocol", "adapter": "pending", "status": "adapter_pending"},
    "memory.project60_outcomes": {"family": "memory", "source": "Project60 OutcomeStore", "adapter": "outcome_store", "status": "runnable"},
    "macro.openbb": {"family": "macro", "source": "OpenBB", "adapter": "pending", "status": "adapter_pending"},
    "macro.grok_research": {"family": "macro", "source": "Grok research bots", "adapter": "pending", "status": "adapter_pending"},
}

# Backward-compatible family view. Individual source identities remain primary.
SPECIALISTS = {
    "technical_patterns": {"family": "technical", "sources": ["pandas-ta-classic", "ta_patterns", "freqtrade/technical", "QuanTAlib", "PyneCore"], "status": "partially_runnable"},
    "strategy_library": {"family": "strategy", "sources": ["PyneCore Strategies", "Freqtrade", "Hummingbot", "Qlib", "RD-Agent", "Forven", "TradingAgents"], "status": "plugin_runtime_ready"},
    "market_structure": {"family": "orderflow", "sources": ["Project60 L2 orderbook", "HyperGrok", "Circuit", "CryptoIntel-MCP", "OFI", "OBI", "Microprice", "VPIN"], "status": "partially_runnable"},
    "derivatives": {"family": "derivatives", "sources": ["Project60 Funding", "Hyperliquid OI", "Liquidations", "Options data"], "status": "adapter_ready_feed_conditional"},
    "forecast": {"family": "forecast", "sources": ["Kronos", "Project60 path forecast"], "status": "runtime_review_pending"},
    "memory": {"family": "memory", "sources": ["TradeMemory protocol", "Project60 OutcomeStore"], "status": "partially_runnable"},
    "macro_news": {"family": "macro", "sources": ["Grok research bots", "OpenBB"], "status": "adapter_pending"},
}


def list_specialists():
    return {key: {**value, "source_ids": tuple(
        brain_id for brain_id, spec in SPECIALIST_SOURCES.items()
        if spec["family"] == value["family"]
    )} for key, value in SPECIALISTS.items()}


def list_specialist_sources():
    return {key: dict(value) for key, value in SPECIALIST_SOURCES.items()}
