import math
import unittest

from mi_core.models import MarketBar
from tools.regime_strategy_analysis import analyze_regimes, classify_regimes


def make_bars(n=800):
    bars = []
    for i in range(n):
        close = 100.0 + 0.06 * i + 2.0 * math.sin(i / 10.0) + 0.5 * math.sin(i / 2.3)
        op = close * (1.0 + 0.001 * math.sin(i / 3.0))
        bars.append(MarketBar(ts=i * 86_400_000, symbol="BTCUSDT", price=close,
                              open=op, high=max(op, close) * 1.004,
                              low=min(op, close) * 0.996, volume=1000.0))
    return bars


class RegimeAnalysisTests(unittest.TestCase):
    def test_regime_labels_are_causal(self):
        bars = make_bars()
        labels = classify_regimes(bars)
        changed = list(bars)
        for i in range(650, len(changed)):
            old = changed[i]
            changed[i] = MarketBar(ts=old.ts, symbol=old.symbol, price=old.price * 1.8,
                                   open=old.open * 1.8, high=old.high * 1.8,
                                   low=old.low * 1.8, volume=old.volume)
        labels_after_future_change = classify_regimes(changed)
        self.assertEqual(labels[:650], labels_after_future_change[:650])

    def test_report_is_research_only_and_contains_regimes(self):
        result = analyze_regimes(make_bars(), cost_round_trip_pct=0.35, capital_usd=500)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertFalse(result["trade_ready"])
        self.assertIn("ema20_50_trend", result["strategy_results"])
        self.assertGreater(result["strategy_results"]["ema20_50_trend"]["oos_bars"], 0)
        self.assertTrue(result["strategy_results"]["ema20_50_trend"]["regimes"])

    def test_insufficient_data_is_not_accepted(self):
        result = analyze_regimes(make_bars(500))
        self.assertEqual(result["status"], "insufficient_data")
        self.assertFalse(result["trade_ready"])


if __name__ == "__main__":
    unittest.main()
