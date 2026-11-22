import unittest
import pandas as pd

from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.freqtrade_adapter import FreqtradeStrategyAdapter


class FakeFreqtradeStrategy:
    def populate_indicators(self, dataframe, metadata):
        self.metadata = metadata
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe["enter_long"] = 1
        dataframe["enter_short"] = 0
        dataframe["mi_confidence"] = 0.82
        dataframe["mi_expected_win_rate"] = 0.65
        dataframe["mi_expected_win_pct"] = 0.8
        dataframe["mi_expected_loss_pct"] = 0.4
        return dataframe


class FreqtradeAdapterTests(unittest.TestCase):
    def test_freqtrade_strategy_runs_as_independent_specialist(self):
        now = 10_000_000
        frame = pd.DataFrame({
            "open": [100.0] * 80, "high": [101.0] * 80,
            "low": [99.0] * 80, "close": [100.0] * 80,
            "volume": [10.0] * 80,
        }, index=[now - 3_600_000 * 80 + i * 3_600_000 for i in range(80)])
        strategy = FakeFreqtradeStrategy()
        adapter = FreqtradeStrategyAdapter(strategy, "strategy.example.freqtrade", "1h")
        result = adapter(MarketSnapshot("BTCUSDT", now, "1h", {
            "ohlcv_by_timeframe": {"1h": frame}
        }))
        self.assertEqual(result.direction, "LONG")
        self.assertEqual(result.confidence, 0.82)
        self.assertEqual(result.expected_win_rate, 0.65)
        self.assertEqual(strategy.metadata, {"pair": "BTCUSDT"})

    def test_stale_freqtrade_frame_is_unavailable(self):
        now = 10_000_000
        frame = pd.DataFrame({
            "open": [100.0], "high": [101.0], "low": [99.0],
            "close": [100.0], "volume": [10.0],
        }, index=[1])
        result = FreqtradeStrategyAdapter(
            FakeFreqtradeStrategy(), "strategy.example.freqtrade", "1h"
        )(MarketSnapshot("BTCUSDT", now, "1h", {"ohlcv_by_timeframe": {"1h": frame}}))
        self.assertFalse(result.available)
        self.assertEqual(result.direction, "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
