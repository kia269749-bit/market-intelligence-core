import unittest
from mi_core.order_flow_economic import evaluate_order_flow_rows, threshold_stability

class OrderFlowEconomicTests(unittest.TestCase):
    def test_flow_can_show_incremental_edge_after_costs(self):
        rows = [
            {"flow_score": 0.8, "base_return_pct": 0.4, "future_return_pct": 0.9},
            {"flow_score": -0.8, "base_return_pct": -0.2, "future_return_pct": -0.7},
        ]
        result = evaluate_order_flow_rows(rows, round_trip_cost_pct=0.35)
        self.assertEqual(result["flow"]["trades"], 2)
        self.assertGreater(result["incremental_net_return_pct"], 0.0)

    def test_threshold_stability_requires_multiple_positive_folds(self):
        rows = [{"flow_score": 0.8, "base_return_pct": 0.4, "future_return_pct": 0.9}]
        result = threshold_stability([{"rows": rows}, {"rows": rows}, {"rows": rows}])
        self.assertTrue(result["thresholds"]["0.2"]["stable"])

if __name__ == "__main__":
    unittest.main()