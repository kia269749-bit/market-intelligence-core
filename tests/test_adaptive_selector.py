import math
import unittest

from mi_core.adaptive_selector import evaluate_adaptive_selection
from mi_core.models import MarketBar


class AdaptiveSelectorTests(unittest.TestCase):
    def _bars(self, n=320, flat=False):
        rows = []
        for i in range(n):
            if flat:
                price = 100.0
            else:
                price = 100.0 * math.exp(0.00015 * i + 0.004 * math.sin(i / 8.0) + 0.0015 * math.sin(i / 2.7))
            rows.append(MarketBar(
                ts=i, symbol="BTC", price=price,
                open=price * (1.0 - 0.0002 * math.sin(i)),
                high=price * 1.001, low=price * 0.999,
                volume=1000.0 + (i % 11),
                buy_volume=120.0 if i % 5 else 60.0,
                sell_volume=60.0 if i % 5 else 120.0,
                oi=10000.0 + i, funding=0.0001,
            ))
        return rows

    def test_selector_returns_candidates_and_walk_forward_metrics(self):
        result = evaluate_adaptive_selection(
            self._bars(), horizon=10, cost_pct=0.35,
            train_window=120, min_train_trades=4, min_oos_trades=3,
        )
        self.assertTrue(result["available"])
        self.assertEqual(len(result["candidates"]), 6)
        self.assertIn(result["status"], ("OOS_EDGE_PASSED", "EDGE_UNPROVEN"))
        self.assertIn("walk_forward_oos", result)
        self.assertGreaterEqual(result["walk_forward_oos"]["trades"], 0)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_flat_market_does_not_prove_a_profitable_edge(self):
        result = evaluate_adaptive_selection(
            self._bars(flat=True), horizon=10, cost_pct=0.35,
            train_window=120, min_train_trades=4, min_oos_trades=3,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["status"], "EDGE_UNPROVEN")

    def test_insufficient_history_is_explicitly_unavailable(self):
        result = evaluate_adaptive_selection(self._bars(n=50), horizon=20)
        self.assertFalse(result["available"])
        self.assertFalse(result["accepted"])
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
