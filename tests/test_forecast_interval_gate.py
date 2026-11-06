import unittest
from unittest.mock import patch

from mi_core.forecast_trade_filter import evaluate_forecast


class ForecastIntervalGateTests(unittest.TestCase):
    def _eligible_policy(self, *args, **kwargs):
        return {"eligible": True, "status": "STRONG", "reason": "test",
                "policy": {"min_confidence": 0.5}}

    def test_up_forecast_uses_lower_interval_bound_for_economic_gate(self):
        forecast = {
            "available": True, "direction": "UP", "confidence": 0.9,
            "expected_return_pct": 1.5, "lower_return_pct": 0.5,
            "upper_return_pct": 2.0,
        }
        with patch("mi_core.forecast_trade_filter.policy_decision", self._eligible_policy):
            result = evaluate_forecast(forecast)
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "expected_move_below_usd4_after_costs")
        self.assertEqual(result["forecast_gate_basis"], "conservative_forecast_interval_bound")
        self.assertEqual(result["expected_move_pct"], 0.5)
        self.assertEqual(result["forecast_point_estimate_pct"], 1.5)

    def test_down_forecast_uses_upper_interval_bound_for_economic_gate(self):
        forecast = {
            "available": True, "direction": "DOWN", "confidence": 0.9,
            "expected_return_pct": -1.5, "lower_return_pct": -2.0,
            "upper_return_pct": -0.5,
        }
        with patch("mi_core.forecast_trade_filter.policy_decision", self._eligible_policy):
            result = evaluate_forecast(forecast)
        self.assertFalse(result["approved"])
        self.assertEqual(result["expected_move_pct"], 0.5)

    def test_invalid_interval_is_rejected(self):
        forecast = {
            "available": True, "direction": "UP", "confidence": 0.9,
            "expected_return_pct": 1.5, "lower_return_pct": 2.0,
            "upper_return_pct": 1.0,
        }
        with patch("mi_core.forecast_trade_filter.policy_decision", self._eligible_policy):
            result = evaluate_forecast(forecast)
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "invalid_forecast_interval")

    def test_legacy_forecast_without_interval_remains_compatible(self):
        forecast = {
            "available": True, "direction": "UP", "confidence": 0.9,
            "expected_return_pct": 1.5,
        }
        with patch("mi_core.forecast_trade_filter.policy_decision", self._eligible_policy):
            result = evaluate_forecast(forecast)
        self.assertEqual(result["forecast_gate_basis"], "point_estimate_legacy_fallback")
        self.assertEqual(result["expected_move_pct"], 1.5)


if __name__ == "__main__":
    unittest.main()
