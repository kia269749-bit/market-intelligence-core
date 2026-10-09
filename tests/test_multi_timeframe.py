import math
import unittest

from mi_core.models import MarketBar
from mi_core.multi_timeframe import analyze_timeframes


class MultiTimeframeTests(unittest.TestCase):
    def _bars(self, interval, n=100, direction=1):
        out = []
        for i in range(n):
            price = 100.0 * math.exp(direction * 0.001 * i)
            previous = 100.0 * math.exp(direction * 0.001 * max(0, i - 1))
            opening = previous if i else price
            out.append(MarketBar(
                ts=i, symbol="BTCUSDT", price=price,
                open=opening,
                high=max(opening, price) * 1.001,
                low=min(opening, price) * 0.999,
                volume=1000.0 + i,
                buy_volume=600.0 if direction > 0 else 400.0,
                sell_volume=400.0 if direction > 0 else 600.0,
            ))
        return out

    def test_multitimeframe_reports_indicators_structure_and_consensus(self):
        result = analyze_timeframes({
            "5m": self._bars("5m", direction=-1),
            "1h": self._bars("1h", direction=1),
            "4h": self._bars("4h", direction=1),
        })
        self.assertTrue(result["available"])
        self.assertEqual(result["bias"], "BULLISH")
        self.assertEqual(result["timeframes"]["5m"]["direction"], "BEARISH")
        self.assertEqual(result["timeframes"]["1h"]["direction"], "BULLISH")
        self.assertEqual(result["timeframes"]["4h"]["direction"], "BULLISH")
        for timeframe in ("5m", "1h", "4h"):
            row = result["timeframes"][timeframe]
            self.assertIn("rsi14", row)
            self.assertIn("atr14_pct", row)
            self.assertIn("support50", row)
            self.assertIn("resistance50", row)
            self.assertIn("candle_pattern", row)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_multitimeframe_requires_at_least_two_usable_intervals(self):
        result = analyze_timeframes({"5m": self._bars("5m", n=40)})
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "fewer_than_two_valid_timeframes")


if __name__ == "__main__":
    unittest.main()
