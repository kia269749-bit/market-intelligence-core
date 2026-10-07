import unittest

from mi_core.economic_edge import diagnose_economic_edge


class EconomicEdgeTests(unittest.TestCase):
    def test_decomposes_cost_magnitude_and_targets(self):
        result = diagnose_economic_edge({
            "predictions": [
                {"pred": 1, "actual_return_pct": 1.20, "favorable_mfe_pct": 1.50, "adverse_mae_pct": 0.20,
                 "p_up": 0.80, "p_flat": 0.10, "p_down": 0.10},
                {"pred": -1, "actual_return_pct": -0.40, "favorable_mfe_pct": 0.70, "adverse_mae_pct": 0.60,
                 "p_up": 0.10, "p_flat": 0.10, "p_down": 0.80},
                {"pred": 1, "actual_return_pct": 0.20, "favorable_mfe_pct": 1.20, "adverse_mae_pct": 0.30,
                 "p_up": 0.65, "p_flat": 0.20, "p_down": 0.15},
            ]
        })
        self.assertEqual(result["samples"], 3)
        self.assertEqual(result["usd4_hit_rate"], 1 / 3)
        self.assertEqual(result["usd10_hit_rate"], 0.0)
        self.assertEqual(result["direction_correct_rate"], 1.0)
        self.assertGreater(result["mfe_reached_usd4_but_horizon_end_missed_rate"], 0.0)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_confidence_buckets_expose_economic_quality(self):
        result = diagnose_economic_edge({
            "predictions": [
                {"pred": 1, "actual_return_pct": 2.50, "favorable_mfe_pct": 2.50, "adverse_mae_pct": 0.10,
                 "p_up": 0.90, "p_flat": 0.05, "p_down": 0.05},
                {"pred": 1, "actual_return_pct": 0.10, "favorable_mfe_pct": 0.20, "adverse_mae_pct": 0.20,
                 "p_up": 0.62, "p_flat": 0.25, "p_down": 0.13},
            ]
        })
        self.assertIn("0.80+", result["confidence_buckets"])
        self.assertIn("0.60-0.69", result["confidence_buckets"])
        self.assertGreater(result["confidence_buckets"]["0.80+"]["net_profit_usd"], 0.0)

    def test_empty_result_is_safe(self):
        result = diagnose_economic_edge({"predictions": []})
        self.assertFalse(result["available"])
        self.assertEqual(result["samples"], 0)
        self.assertIn("insufficient_directional_oos_rows", result["diagnostic_hypotheses"])


if __name__ == "__main__":
    unittest.main()
