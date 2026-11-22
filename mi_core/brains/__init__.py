"""Composable specialist brains and central signal arbiter for Project60."""
from .callable_adapters import CallableForecastAdapter, CallableStrategyAdapter, OpenBBMacroAdapter, register_callable_strategy
from .contracts import BrainProposal, BrainResult, MarketSnapshot
from .engine import SignalReport, evaluate_brains
from .freqtrade_adapter import FreqtradeStrategyAdapter, register_freqtrade_strategy
from .orchestrator import arbitrate
from .hyperliquid_feed import fetch_hyperliquid_brain_context, fetch_hyperliquid_brain_contexts
from .signal_journal import SignalJournal
from .strategy_runtime import StrategyRegistration, StrategyRuntime

__all__ = [
    "BrainProposal", "BrainResult", "MarketSnapshot", "SignalReport", "CallableForecastAdapter", "CallableStrategyAdapter", "OpenBBMacroAdapter", "register_callable_strategy",
    "FreqtradeStrategyAdapter", "SignalJournal", "StrategyRegistration", "StrategyRuntime", "register_freqtrade_strategy", "arbitrate", "evaluate_brains", "fetch_hyperliquid_brain_context", "fetch_hyperliquid_brain_contexts",
]
