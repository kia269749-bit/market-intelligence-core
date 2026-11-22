"""Declarative specialist source registry; adapters are enabled only when implemented."""
SPECIALISTS = {
    "technical_patterns": {"family": "technical", "sources": ["indicator_brain", "pandas-ta-classic", "ta_patterns", "freqtrade/technical", "QuanTAlib", "PyneCore"], "status": "adapter_pending"},
    "strategy_library": {"family": "strategy", "sources": ["PyneCore Strategies", "Freqtrade", "Hummingbot", "Qlib", "RD-Agent", "Forven", "TradingAgents"], "status": "adapter_pending"},
    "market_structure": {"family": "orderflow", "sources": ["HyperGrok read-only schemas", "Circuit framework", "OFI", "OBI", "Microprice", "VPIN"], "status": "adapter_pending"},
    "derivatives": {"family": "derivatives", "sources": ["Project60 Funding", "Hyperliquid OI", "Liquidations", "Options data"], "status": "adapter_pending"},
    "forecast": {"family": "forecast", "sources": ["Kronos", "Project60 path forecast"], "status": "adapter_pending"},
    "memory": {"family": "memory", "sources": ["TradeMemory protocol", "Project60 OutcomeStore"], "status": "native_foundation"},
    "macro_news": {"family": "macro", "sources": ["Grok research bots", "OpenBB"], "status": "adapter_pending"},
}

def list_specialists():
    return {key: {"family": value["family"], "sources": tuple(value["sources"]), "status": value["status"]} for key, value in SPECIALISTS.items()}
