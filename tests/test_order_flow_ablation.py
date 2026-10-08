import unittest

from mi_core.order_flow_ablation import evaluate_oos_ablation


class OrderFlowAblationTests(unittest.TestCase):
    def test_chronological_folds_do_not_use_future_rows(self):
        rows = [
            {"base_return_pct": 1.0, "flow_score": 1.0, "future_return_pct": 0.8},
            {"base_return_pct": 1.0, "flow_score": 1.0, "future_return_pct": 0.7},
            {"base_return_pct": -1.0, "flow_score": -1.0, "future_return_pct": -0.8},
            {"base_return_pct": -1.0, "flow_score": -1.0, "future_return_pct": -0.7},
            {"base_return_pct": 1.0, "flow_score": 1.0, "future_return_pct": 0.9},
            {"base_return_pct": -1.0, "flow_score": -1.0, "future_return_pct": -0.9},
        ]
        timestamps = [1, 2, 3, 4, 5, 6]
        result = evaluate_oos_ablation(
            rows, timestamps, train_size=2, test_size=2, step=2,
            thresholds=(0.2,), round_trip_cost_pct=0.1,
        )
        self.assertEqual(len(result["thresholds"]["0.2"]["folds"]), 2)
        self.assertEqual(result["thresholds"]["0.2"]["folds"][0]["test_start"], 2)
        self.assertEqual(result["thresholds"]["0.2"]["folds"][1]["test_start"], 4)

    def test_bad_lengths_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_oos_ablation([], [1], train_size=1, test_size=1)


if __name__ == "__main__":
    unittest.main()
