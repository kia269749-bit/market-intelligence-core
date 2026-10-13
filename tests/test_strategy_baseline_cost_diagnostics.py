import math
import unittest

from mi_core.models import MarketBar
from tools.strategy_baseline_cost_diagnostics import COSTS, build_report


class StrategyBaselineCostDiagnosticsTests(unittest.TestCase):
    def _bars(self, n=500):
        rows = []
        for i in range(n):
            price = 100.0 * math.exp(
                0.0001 * i + 0.006 * math.sin(i / 8.0)
                + 0.001 * math.sin(i / 2.3)
            )
            rows.append(MarketBar(
                ts=i, symbol="BTCUSDT", price=price,
                open=price * (1.0 - 0.0002 * math.sin(i)),
                high=price * 1.001, low=price * 0.999,
                volume=1000.0 + (i % 11),
                buy_volume=120.0 if i % 5 else 60.0,
                sell_volume=60.0 if i % 5 else 120.0,
                oi=10000.0 + i, funding=0.0001,
            ))
        return rows

    def test_costs_baselines_definitions_and_research_only(self):
        result = build_report(self._bars(), horizon=10, iterations=100, seed=42)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["cost_sensitivity_round_trip_pct"], list(COSTS))
        self.assertEqual(len(result["strategy_families"]), 11)
        sample = result["strategy_families"]["momentum_5"]["segments"]["development"]
        self.assertEqual(set(sample["by_cost"]), {str(x) for x in COSTS})
        metric = sample["by_cost"]["0.2"]["strategy_metrics"]
        self.assertIn("ci_lower_pct", metric)
        random_baseline = sample["by_cost"]["0.2"]["random_entry_baseline"]
        self.assertIn("random_mean_ge_strategy_p", random_baseline)
        self.assertIn("buy_and_hold_net_pct_by_cost", sample)
        self.assertIn("ci_lower_pct", result["metric_definitions"])
        self.assertFalse(result["accepted"])
        self.assertFalse(result["live_orders"])
        self.assertTrue(result["research_only"])

    def test_insufficient_data_never_accepted(self):
        result = build_report(self._bars(n=50), horizon=10, iterations=100)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertFalse(result["accepted"])


if __name__ == "__main__":
    unittest.main()
