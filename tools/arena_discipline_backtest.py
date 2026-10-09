"""Compatibility wrapper for the shared arena-discipline research module."""
from mi_core.arena_discipline_backtest import (
    _base_signals,
    _confirmation_filter,
    _patience_filter,
    compare_arms,
)

__all__ = ["compare_arms"]
