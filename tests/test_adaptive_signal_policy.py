import unittest

from mi_core.adaptive_signal_policy import get_signal_policy, policy_decision
from mi_core.forecast_trade_filter import evaluate_forecast


class AdaptiveSignalPolicyTests(unittest.TestCase):
    def test_trend_is_more_permissive_than_range(self):
        trend = get_signal_policy("TREND")
        range_policy = get_signal_policy("RANGE")
        self.assertLess(trend.watch_confidence, range_policy.watch_confidence)

    def test_clean_trend_can_surface_watch(self):
        result = policy_decision(
            0.61, "UP", regime="TREND", quality_score=1.0, agreement=0.85
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["status"], "WATCH")

    def test_range_stays_selective(self):
        result = policy_decision(
            0.61, "UP", regime="RANGE", quality_score=1.0, agreement=0.85
        )
        self.assertFalse(result["eligible"])
        self.assertEqual(result["status"], "NO_TRADE")

    def test_conflicting_sources_block(self):
        result = policy_decision(
            0.75, "UP", regime="TREND", quality_score=1.0, agreement=0.50
        )
        self.assertFalse(result["eligible"])

    def test_economic_floor_still_applies(self):
        forecast = {
            "available": True, "direction": "UP",
            "confidence": 0.70, "expected_return_pct": 0.30
        }
        result = evaluate_forecast(
            forecast, regime="TREND", quality_score=1.0, agreement=0.85
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["status"], "NO_TRADE")

    def test_subfloor_opportunity_stays_below_economic_floor(self):
        forecast = {
            "available": True, "direction": "UP",
            "confidence": 0.92, "expected_return_pct": 0.30
        }
        result = evaluate_forecast(
            forecast, regime="TREND", quality_score=1.0, agreement=0.62
        )
        self.assertFalse(result["approved"])
        self.assertEqual(result["status"], "NO_TRADE")

    def test_economic_watch_can_pass_with_adaptive_confidence(self):
        forecast = {
            "available": True, "direction": "UP",
            "confidence": 0.61, "expected_return_pct": 1.5
        }
        result = evaluate_forecast(
            forecast, regime="TREND", quality_score=1.0, agreement=0.85
        )
        self.assertTrue(result["approved"])
        self.assertEqual(result["status"], "WATCH")


if __name__ == "__main__":
    unittest.main()
