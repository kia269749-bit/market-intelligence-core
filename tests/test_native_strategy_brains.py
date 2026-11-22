import unittest
import pandas as pd

from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.native_strategy_brains import evaluate_native_ohlcv_strategies


class NativeStrategyBrainTests(unittest.TestCase):
    def test_six_native_strategy_brains_run_independently_on_fresh_ohlcv(self):
        n = 140
        index = [1_000_000 + i * 3_600_000 for i in range(n)]
        close = [100.0 + i * 0.25 for i in range(n)]
        frame = pd.DataFrame({
            "open": [x - 0.1 for x in close],
            "high": [x + 0.3 for x in close],
            "low": [x - 0.3 for x in close],
            "close": close,
            "volume": [1000.0 + i * 2 for i in range(n)],
        }, index=index)
        snapshot = MarketSnapshot("BTCUSDT", index[-1] + 3_600_000 + 1000, "1h", {
            "ohlcv_by_timeframe": {"1h": frame}
        })
        rows = evaluate_native_ohlcv_strategies(snapshot)
        ids = {row.brain_id for row in rows}
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(ids), 6)
        self.assertTrue(all(row.family == "technical" for row in rows))
        self.assertTrue(any(row.direction == "LONG" for row in rows))

    def test_stale_ohlcv_does_not_generate_strategy_votes(self):
        n = 140
        index = [1_000_000 + i * 3_600_000 for i in range(n)]
        close = [100.0 + i * 0.25 for i in range(n)]
        frame = pd.DataFrame({
            "open": close, "high": [x + 1 for x in close],
            "low": [x - 1 for x in close], "close": close,
            "volume": [1000.0] * n,
        }, index=index)
        rows = evaluate_native_ohlcv_strategies(MarketSnapshot(
            "BTCUSDT", index[-1] + 20 * 3_600_000, "1h",
            {"ohlcv_by_timeframe": {"1h": frame}},
        ))
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
