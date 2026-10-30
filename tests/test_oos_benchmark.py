import unittest
from mi_core.oos_benchmark import compare_oos_baselines


class OOSBenchmarkTests(unittest.TestCase):
    def test_cost_and_non_overlap_and_baselines(self):
        result = {
            "horizon_bars": 2,
            "bar_interval_ms": 60_000,
            "predictions": [
                {"ts": 0, "pred": 1, "actual_return_pct": 1.0},
                {"ts": 60_000, "pred": -1, "actual_return_pct": -1.0},
                {"ts": 120_000, "pred": -1, "actual_return_pct": 0.5},
            ],
        }
        out = compare_oos_baselines(result, cost_policy="strict", seed=7)
        self.assertEqual(out["non_overlapping_oos_samples"], 2)
        # Model: (1.00-.45) + (-.50-.45) = -0.40% of $500 = -$2.00
        self.assertAlmostEqual(out["model"]["net_profit_usd"], -2.0)
        # Buy-and-hold: (1.00-.45) + (.50-.45) = .60% of $500 = $3.00
        self.assertAlmostEqual(out["buy_and_hold"]["net_profit_usd"], 3.0)
        self.assertEqual(out["round_trip_cost_pct"], 0.45)
        self.assertTrue(out["research_only"])
        self.assertFalse(out["live_orders"])

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            compare_oos_baselines({"predictions": []}, cost_policy="other")


if __name__ == "__main__":
    unittest.main()
