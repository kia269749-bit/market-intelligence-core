from types import SimpleNamespace
import numpy as np
import pandas as pd

from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.ta_patterns_adapter import evaluate_ta_patterns_specialists


def _frame(as_of_ms):
    start = as_of_ms - 20 * 900_000
    index = [start + i * 900_000 for i in range(20)]
    return pd.DataFrame({
        "open": np.arange(20, dtype=float) + 100,
        "high": np.arange(20, dtype=float) + 102,
        "low": np.arange(20, dtype=float) + 99,
        "close": np.arange(20, dtype=float) + 101,
        "volume": np.full(20, 10.0),
    }, index=index)


def test_emits_separate_brain_for_each_fired_directional_pattern(monkeypatch):
    as_of = 20 * 900_000
    fake = SimpleNamespace(
        NON_DIRECTIONAL=frozenset({"doji"}),
        scan_all_patterns=lambda *args, **kwargs: {
            "hammer": np.array([0] * 19 + [1], dtype=np.int8),
            "engulfing_bearish": np.array([0] * 19 + [-1], dtype=np.int8),
            "doji": np.array([0] * 19 + [1], dtype=np.int8),
            "inactive": np.zeros(20, dtype=np.int8),
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "ta_patterns", fake)
    snapshot = MarketSnapshot("BTCUSDT", as_of, "15m", {"ohlcv_by_timeframe": {"15m": _frame(as_of)}})
    proposals = evaluate_ta_patterns_specialists(snapshot)
    assert {p.brain_id for p in proposals} == {
        "pattern.ta_patterns.hammer.15m",
        "pattern.ta_patterns.engulfing_bearish.15m",
    }
    assert {p.direction for p in proposals} == {"LONG", "SHORT"}
    assert all(p.family == "technical" and p.as_of_ms == as_of for p in proposals)


def test_rejects_forming_or_stale_candles(monkeypatch):
    fake = SimpleNamespace(
        NON_DIRECTIONAL=frozenset(),
        scan_all_patterns=lambda *args, **kwargs: {"hammer": np.array([1], dtype=np.int8)},
    )
    monkeypatch.setitem(__import__("sys").modules, "ta_patterns", fake)
    as_of = 20 * 900_000
    stale = _frame(as_of)
    stale.index = stale.index - 3 * 900_000
    snapshot = MarketSnapshot("BTCUSDT", as_of, "15m", {"ohlcv_by_timeframe": {"15m": stale}})
    assert evaluate_ta_patterns_specialists(snapshot) == []
