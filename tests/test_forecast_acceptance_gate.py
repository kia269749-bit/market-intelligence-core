import unittest

from mi_core.validated_forecast import forecast_acceptance_gate


class ForecastAcceptanceGateTests(unittest.TestCase):
    def setUp(self):
        self.metrics = {
            "resolved": 100,
            "high_conf_samples": 20,
            "high_conf_accuracy": 0.60,
        }
        self.capital = {
            "min_target_hit_rate": 0.40,
            "preferred_target_hit_rate": 0.20,
        }
        self.good_economics = {
            "net_profit_usd": 8.0,
            "expectancy_usd": 0.5,
            "max_drawdown_usd": 3.0,
        }
        self.good_thresholds = {
            "min_net_profit_usd": 4.0,
            "min_expectancy_usd": 0.1,
            "max_drawdown_usd": 5.0,
        }

    def gate(self, **kwargs):
        return forecast_acceptance_gate(
            self.metrics, self.capital, **kwargs
        )

    def test_legacy_behavior_without_economic_thresholds(self):
        result = self.gate()
        self.assertTrue(result["accepted"])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_economic_checks_are_opt_in(self):
        result = self.gate(economic_metrics=None)
        self.assertTrue(result["accepted"])

    def test_missing_economic_payload_is_rejected_when_enabled(self):
        result = self.gate(min_net_profit_usd=1.0)
        self.assertFalse(result["accepted"])
        self.assertIn("invalid_economic_metrics_payload", result["reasons"])

    def test_non_dict_economic_payload_is_rejected(self):
        result = self.gate(
            economic_metrics=[],
            min_net_profit_usd=1.0,
        )
        self.assertFalse(result["accepted"])
        self.assertIn("invalid_economic_metrics_payload", result["reasons"])

    def test_positive_economic_metrics_pass(self):
        result = self.gate(
            economic_metrics=self.good_economics,
            **self.good_thresholds,
        )
        self.assertTrue(result["accepted"], result["reasons"])
        self.assertEqual(result["status"], "PASS")

    def test_low_profit_expectancy_and_excessive_drawdown_reject(self):
        result = self.gate(
            economic_metrics={
                "net_profit_usd": -1.0,
                "expectancy_usd": -0.1,
                "max_drawdown_usd": 9.0,
            },
            **self.good_thresholds,
        )
        self.assertFalse(result["accepted"])
        for reason in (
            "insufficient_net_profit_usd",
            "insufficient_expectancy_usd",
            "excessive_drawdown_usd",
        ):
            self.assertIn(reason, result["reasons"])

    def test_missing_active_metric_rejects(self):
        cases = (
            ("net_profit_usd", "min_net_profit_usd",
             "missing_or_invalid_net_profit_usd"),
            ("expectancy_usd", "min_expectancy_usd",
             "missing_or_invalid_expectancy_usd"),
            ("max_drawdown_usd", "max_drawdown_usd",
             "missing_or_invalid_drawdown_usd"),
        )
        for metric_key, threshold_key, reason in cases:
            with self.subTest(metric=metric_key):
                economics = dict(self.good_economics)
                economics.pop(metric_key)
                result = self.gate(
                    economic_metrics=economics,
                    **{threshold_key: 1.0},
                )
                self.assertFalse(result["accepted"])
                self.assertIn(reason, result["reasons"])

    def test_nan_net_threshold_rejected(self):
        result = self.gate(
            economic_metrics=self.good_economics,
            min_net_profit_usd=float("nan"),
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "invalid_min_net_profit_usd_threshold", result["reasons"]
        )

    def test_inf_expectancy_threshold_rejected(self):
        result = self.gate(
            economic_metrics=self.good_economics,
            min_expectancy_usd=float("inf"),
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "invalid_min_expectancy_usd_threshold", result["reasons"]
        )

    def test_negative_drawdown_threshold_rejected(self):
        result = self.gate(
            economic_metrics=self.good_economics,
            max_drawdown_usd=-1.0,
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "invalid_max_drawdown_usd_threshold", result["reasons"]
        )

    def test_string_threshold_rejected(self):
        result = self.gate(
            economic_metrics=self.good_economics,
            min_net_profit_usd="4",
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "invalid_min_net_profit_usd_threshold", result["reasons"]
        )

    def test_string_metric_rejected(self):
        economics = dict(self.good_economics)
        economics["net_profit_usd"] = "8"
        result = self.gate(
            economic_metrics=economics,
            min_net_profit_usd=4.0,
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "missing_or_invalid_net_profit_usd", result["reasons"]
        )

    def test_bool_metric_rejected(self):
        economics = dict(self.good_economics)
        economics["net_profit_usd"] = True
        result = self.gate(
            economic_metrics=economics,
            min_net_profit_usd=4.0,
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "missing_or_invalid_net_profit_usd", result["reasons"]
        )

    def test_non_finite_metric_rejected(self):
        cases = (
            ("net_profit_usd", float("nan"),
             "missing_or_invalid_net_profit_usd"),
            ("expectancy_usd", float("inf"),
             "missing_or_invalid_expectancy_usd"),
        )
        for metric_key, value, reason in cases:
            with self.subTest(metric=metric_key):
                economics = dict(self.good_economics)
                economics[metric_key] = value
                result = self.gate(
                    economic_metrics=economics,
                    **self.good_thresholds,
                )
                self.assertFalse(result["accepted"])
                self.assertIn(reason, result["reasons"])

    def test_negative_drawdown_metric_rejected(self):
        economics = dict(self.good_economics)
        economics["max_drawdown_usd"] = -1.0
        result = self.gate(
            economic_metrics=economics,
            max_drawdown_usd=5.0,
        )
        self.assertFalse(result["accepted"])
        self.assertIn(
            "missing_or_invalid_drawdown_usd", result["reasons"]
        )

    def test_invalid_thresholds_are_rejected(self):
        cases = (
            ("min_net_profit_usd", "4",
             "invalid_min_net_profit_usd_threshold"),
            ("min_expectancy_usd", float("inf"),
             "invalid_min_expectancy_usd_threshold"),
            ("max_drawdown_usd", -1.0,
             "invalid_max_drawdown_usd_threshold"),
        )
        for threshold_key, value, reason in cases:
            with self.subTest(threshold=threshold_key):
                result = self.gate(
                    economic_metrics=self.good_economics,
                    **{threshold_key: value},
                )
                self.assertFalse(result["accepted"])
                self.assertIn(reason, result["reasons"])

    def test_multiple_rejection_reasons_accumulate(self):
        result = self.gate(
            economic_metrics={
                "net_profit_usd": -1.0,
                "expectancy_usd": -1.0,
                "max_drawdown_usd": 10.0,
            },
            **self.good_thresholds,
        )
        self.assertFalse(result["accepted"])
        self.assertGreaterEqual(len(result["reasons"]), 3)

    def test_research_safety_flags_remain_locked(self):
        result = self.gate(
            economic_metrics=self.good_economics,
            **self.good_thresholds,
        )
        self.assertIs(result["research_only"], True)
        self.assertIs(result["live_orders"], False)


if __name__ == "__main__":
    unittest.main()
