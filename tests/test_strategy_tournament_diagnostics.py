import math
import unittest

from mi_core.models import MarketBar
from tools.strategy_tournament_diagnostics import evaluate


class StrategyTournamentDiagnosticsTests(unittest.TestCase):
    def _bars(self, n=420):
        rows = []
        for i in range(n):
            price = 100.0 * math.exp(0.0003 * i + 0.006 * math.sin(i / 9.0))
            rows.append(MarketBar(
                ts=i, symbol="BTCUSDT", price=price,
                open=price * (1.0 - 0.0003),
                high=price * 1.001, low=price * 0.999,
                volume=1000.0, buy_volume=120.0, sell_volume=80.0,
                oi=10000.0 + i, funding=0.0001,
            ))
        return rows

    def test_screen_reports_each_strategy_and_windows_without_approval(self):
        result = evaluate(self._bars(), horizon=10, cost_pct=0.35,
                          holdout_bars=240, windows=3)
        self.assertTrue(result["available"])
        self.assertEqual(len(result["strategies"]), 11)
        self.assertEqual(len(result["ranking"]), 11)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertIn("MULTIPLE_COMPARISON_BIAS", result["interpretation"])
        for metrics in result["strategies"].values():
            self.assertEqual(len(metrics["window_metrics"]), 3)
            self.assertGreaterEqual(metrics["trades"], 0)

    def test_insufficient_history_is_not_misrepresented_as_validated(self):
        result = evaluate(self._bars(n=100), horizon=10, cost_pct=0.35,
                          holdout_bars=240, windows=3)
        self.assertFalse(result["available"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
