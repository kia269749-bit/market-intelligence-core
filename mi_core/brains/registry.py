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
    "technical.strategy.ema_trend.15m": {"family": "technical", "source": "Project60 OHLCV native strategy ema_trend", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_momentum.15m": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_reversion.15m": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.donchian_breakout.15m": {"family": "technical", "source": "Project60 OHLCV native strategy donchian_breakout", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.macd_momentum.15m": {"family": "technical", "source": "Project60 OHLCV native strategy macd_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.bollinger_reversion.15m": {"family": "technical", "source": "Project60 OHLCV native strategy bollinger_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.ema_trend.1h": {"family": "technical", "source": "Project60 OHLCV native strategy ema_trend", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_momentum.1h": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_reversion.1h": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.donchian_breakout.1h": {"family": "technical", "source": "Project60 OHLCV native strategy donchian_breakout", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.macd_momentum.1h": {"family": "technical", "source": "Project60 OHLCV native strategy macd_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.bollinger_reversion.1h": {"family": "technical", "source": "Project60 OHLCV native strategy bollinger_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.ema_trend.4h": {"family": "technical", "source": "Project60 OHLCV native strategy ema_trend", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_momentum.4h": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_reversion.4h": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.donchian_breakout.4h": {"family": "technical", "source": "Project60 OHLCV native strategy donchian_breakout", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.macd_momentum.4h": {"family": "technical", "source": "Project60 OHLCV native strategy macd_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.bollinger_reversion.4h": {"family": "technical", "source": "Project60 OHLCV native strategy bollinger_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.ema_trend.1d": {"family": "technical", "source": "Project60 OHLCV native strategy ema_trend", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_momentum.1d": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.rsi_reversion.1d": {"family": "technical", "source": "Project60 OHLCV native strategy rsi_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.donchian_breakout.1d": {"family": "technical", "source": "Project60 OHLCV native strategy donchian_breakout", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.macd_momentum.1d": {"family": "technical", "source": "Project60 OHLCV native strategy macd_momentum", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.strategy.bollinger_reversion.1d": {"family": "technical", "source": "Project60 OHLCV native strategy bollinger_reversion", "adapter": "native_strategy_brains", "status": "runnable_when_ohlcv_present"},
    "technical.ta_patterns.dynamic": {"family": "technical", "source": "AdventuresInDataScience/ta_patterns (300 pattern detectors)", "adapter": "ta_patterns_adapter", "status": "runnable_when_ohlcv_present; dynamic per-pattern/timeframe IDs"},
    "strategy.pynecore": {"family": "strategy", "source": "theonetrade/pynecore-strategies", "adapter": "callable_adapters", "status": "callable_adapter_runtime_required"},
    "strategy.freqtrade": {"family": "strategy", "source": "freqtrade/freqtrade", "adapter": "freqtrade_adapter", "status": "adapter_available_source_review_required"},
    "strategy.hummingbot": {"family": "strategy", "source": "hummingbot/hummingbot", "adapter": "strategy_runtime", "status": "plugin_ready"},
    "strategy.qlib": {"family": "strategy", "source": "microsoft/qlib", "adapter": "callable_adapters", "status": "callable_model_runtime_required"},
    "strategy.rd_agent": {"family": "strategy", "source": "microsoft/RD-Agent", "adapter": "callable_adapters", "status": "callable_model_runtime_required"},
    "strategy.tradingagents": {"family": "strategy", "source": "TauricResearch/TradingAgents", "adapter": "callable_adapters", "status": "callable_agent_runtime_required"},
    "strategy.forven": {"family": "strategy", "source": "judder659/Forven", "adapter": "strategy_runtime", "status": "license_review_required"},
    "market.orderbook_imbalance": {"family": "orderflow", "source": "Hyperliquid public l2Book normalized L2 bids/asks", "adapter": "hyperliquid_feed+orderbook_adapter", "status": "runnable_when_feed_present"},
    "market.project60_orderbook_imbalance": {"family": "orderflow", "source": "Project60 orderbook imbalance snapshot", "adapter": "project60_flow_adapter", "status": "runnable_when_feed_present"},
    "market.project60_trade_flow": {"family": "orderflow", "source": "Project60 executed-trade imbalance snapshot", "adapter": "project60_flow_adapter", "status": "runnable_when_feed_present"},
    "market.hypergrok": {"family": "orderflow", "source": "galleonlabs/hypergrok-trading-desk", "adapter": "pending", "status": "adapter_pending"},
    "market.circuit": {"family": "orderflow", "source": "EthanXiang777/circuit-framework", "adapter": "pending", "status": "adapter_pending"},
    "market.cryptointel_mcp": {"family": "orderflow", "source": "Arshad-13/CryptoIntel-MCP", "adapter": "pending", "status": "adapter_pending"},
    "derivatives.hyperliquid_funding": {"family": "derivatives", "source": "Project60 settled FundingEvent", "adapter": "derivatives_adapter", "status": "runnable_when_feed_present"},
    "derivatives.open_interest": {"family": "derivatives", "source": "Hyperliquid public metaAndAssetCtxs OI delta + mark price", "adapter": "hyperliquid_feed+derivatives_adapter", "status": "runnable_when_feed_present"},
    "forecast.kronos": {"family": "forecast", "source": "shiyu-coder/Kronos", "adapter": "CallableForecastAdapter", "status": "model_runtime_required"},
    "memory.tradememory": {"family": "memory", "source": "mnemox-ai/tradememory-protocol", "adapter": "pending", "status": "adapter_pending"},
    "memory.project60_outcomes": {"family": "memory", "source": "Project60 OutcomeStore", "adapter": "outcome_store", "status": "runnable"},
    "macro.openbb": {"family": "macro", "source": "OpenBB timestamped macro_context", "adapter": "OpenBBMacroAdapter", "status": "runnable_when_feed_present"},
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
