import unittest

from mi_core.research_quality_gate import (
    evaluate_cost_sensitivity,
    evaluate_research_quality,
)


class ResearchQualityGateTests(unittest.TestCase):
    def _good_inputs(self):
        return (
            {"resolved": 120, "high_conf_samples": 30, "high_conf_accuracy": 0.70},
            {"net_profit_usd": 80.0, "expectancy_usd": 0.66, "profit_factor": 1.35},
            {"min_target_hit_rate": 0.35, "preferred_target_hit_rate": 0.20},
            {"resolved": 120, "model_vs_majority_accuracy_lift": 0.08,
             "class_collapse": False, "overlap_rate": 0.0},
        )

    def _robustness(self):
        return {
            "preregistered": True,
            "data_provenance_verified": True,
            "parameter_plateau_passed": True,
            "multiple_testing_adjusted": True,
            "baseline_bootstrap_ci_lower": 0.01,
            "positive_regime_fraction": 0.75,
        }

    def test_cost_sensitivity_uses_central_and_separate_high_cost_scenario(self):
        result = {"predictions": [
            {"pred": 1, "actual_return_pct": 2.0},
            {"pred": -1, "actual_return_pct": -2.0},
        ]}
        metrics = evaluate_cost_sensitivity(result, 500.0, 0.24)
        self.assertEqual(metrics["scenarios"]["central"]["round_trip_cost_pct"], 0.24)
        self.assertEqual(metrics["scenarios"]["stress_1_5x"]["round_trip_cost_pct"], 0.36)
        self.assertEqual(metrics["scenarios"]["stress_2x"]["round_trip_cost_pct"], 0.48)
        self.assertEqual(metrics["scenarios"]["user_high_cost_sensitivity_20pct_rt"]["round_trip_cost_pct"], 20.0)
        self.assertFalse(metrics["scenarios"]["user_high_cost_sensitivity_20pct_rt"]["profitable"])
        self.assertTrue(metrics["research_only"])
        self.assertFalse(metrics["live_orders"])

    def test_complete_positive_evidence_can_pass(self):
        predictions, economics, capital, integrity = self._good_inputs()
        costs = {"scenarios": {
            "stress_1_5x": {"profitable": True},
            "stress_2x": {"profitable": True},
        }}
        gate = evaluate_research_quality(
            predictions, economics, capital, integrity, costs, self._robustness()
        )
        self.assertEqual(gate["status"], "PASS")
        self.assertEqual(gate["blockers"], [])
        self.assertEqual(gate["missing_evidence"], [])
        self.assertTrue(gate["research_only"])
        self.assertFalse(gate["live_orders"])

    def test_missing_preregistered_robustness_fails_closed(self):
        predictions, economics, capital, integrity = self._good_inputs()
        costs = {"scenarios": {
            "stress_1_5x": {"profitable": True},
            "stress_2x": {"profitable": True},
        }}
        gate = evaluate_research_quality(predictions, economics, capital, integrity, costs)
        self.assertEqual(gate["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("preregistration_missing", gate["missing_evidence"])
        self.assertNotIn("PASS", [gate["status"]])

    def test_negative_net_profit_rejects_even_if_other_evidence_is_positive(self):
        predictions, economics, capital, integrity = self._good_inputs()
        economics["net_profit_usd"] = -1.0
        costs = {"scenarios": {
            "stress_1_5x": {"profitable": True},
            "stress_2x": {"profitable": True},
        }}
        gate = evaluate_research_quality(
            predictions, economics, capital, integrity, costs, self._robustness()
        )
        self.assertEqual(gate["status"], "REJECT")
        self.assertIn("nonpositive_net_profit", gate["blockers"])

    def test_overlapping_oos_samples_without_adjustment_are_rejected(self):
        predictions, economics, capital, integrity = self._good_inputs()
        integrity["overlap_rate"] = 0.25
        costs = {"scenarios": {
            "stress_1_5x": {"profitable": True},
            "stress_2x": {"profitable": True},
        }}
        gate = evaluate_research_quality(
            predictions, economics, capital, integrity, costs, self._robustness()
        )
        self.assertEqual(gate["status"], "REJECT")
        self.assertIn(
            "overlapping_oos_samples_without_dependence_adjustment", gate["blockers"]
        )


if __name__ == "__main__":
    unittest.main()
