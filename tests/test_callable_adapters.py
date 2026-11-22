import unittest
import pandas as pd

from mi_core.brains.callable_adapters import (
    CallableForecastAdapter, CallableStrategyAdapter, OpenBBMacroAdapter,
)
from mi_core.brains.contracts import MarketSnapshot


def fresh_frame(now):
    index = [now - 80 * 3_600_000 + i * 3_600_000 for i in range(80)]
    return pd.DataFrame({
        "open": [100.0] * 80, "high": [101.0] * 80,
        "low": [99.0] * 80, "close": [100.0] * 80,
        "volume": [10.0] * 80,
    }, index=index)


class CallableAdapterTests(unittest.TestCase):
    def test_callable_strategy_maps_external_python_strategy(self):
        now = 20_000_000
        adapter = CallableStrategyAdapter(
            lambda frame, meta: {"direction": "SHORT", "confidence": 0.78, "reasons": ["test"]},
            "strategy.pynecore.test", "theonetrade/pynecore-strategies", "1h",
        )
        result = adapter(MarketSnapshot("BTCUSDT", now, "1h", {
            "ohlcv_by_timeframe": {"1h": fresh_frame(now)}
        }))
        self.assertEqual(result.direction, "SHORT")
        self.assertEqual(result.family, "strategy")
        self.assertEqual(result.confidence, 0.78)

    def test_callable_forecast_model_maps_up_probability(self):
        now = 20_000_000
        adapter = CallableForecastAdapter(
            lambda frame: {"up_probability": 0.70, "expected_win_pct": 0.8, "expected_loss_pct": 0.4},
            "forecast.kronos", "shiyu-coder/Kronos", "1h",
        )
        result = adapter(MarketSnapshot("BTCUSDT", now, "1h", {
            "ohlcv_by_timeframe": {"1h": fresh_frame(now)}
        }))
        self.assertEqual(result.direction, "LONG")
        self.assertGreaterEqual(result.confidence, 0.55)
        self.assertEqual(result.expected_win_rate, 0.70)

    def test_openbb_macro_requires_fresh_timestamped_context(self):
        now = 20_000_000
        adapter = OpenBBMacroAdapter()
        fresh = adapter(MarketSnapshot("BTCUSDT", now, "1h", {
            "macro_context": {"timestamp_ms": now - 1000, "direction_score": 0.8}
        }))
        stale = adapter(MarketSnapshot("BTCUSDT", now, "1h", {
            "macro_context": {"timestamp_ms": now - 7 * 3_600_000, "direction_score": 0.8}
        }))
        self.assertEqual(fresh.direction, "LONG")
        self.assertFalse(stale.available)


if __name__ == "__main__":
    unittest.main()
