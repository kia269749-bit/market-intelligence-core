import unittest

from mi_core.fomo_outcome import evaluate_fomo_outcome, summarize_fomo_outcomes


class FomoOutcomeTests(unittest.TestCase):
    def test_outcome_tracks_future_path(self):
        result = evaluate_fomo_outcome(100, [103, 108, 104], target_pct=5, stop_pct=-5)
        self.assertEqual(result.horizon, 3)
        self.assertEqual(result.return_pct, 4.0)
        self.assertEqual(result.max_up_pct, 8.0)
        self.assertEqual(result.max_down_pct, 3.0)
        self.assertTrue(result.hit_target)
        self.assertFalse(result.hit_stop)

    def test_horizon_limits_path(self):
        result = evaluate_fomo_outcome(100, [110, 90, 120], horizon=2)
        self.assertEqual(result.horizon, 2)
        self.assertEqual(result.return_pct, -10.0)
        self.assertTrue(result.hit_target)
        self.assertTrue(result.hit_stop)

    def test_summary(self):
        outcomes = [
            evaluate_fomo_outcome(100, [105]),
            evaluate_fomo_outcome(100, [95]),
        ]
        summary = summarize_fomo_outcomes(outcomes)
        self.assertEqual(summary["events"], 2)
        self.assertEqual(summary["mean_return_pct"], 0.0)
        self.assertEqual(summary["positive_return_rate"], 0.5)

    def test_invalid_prices(self):
        with self.assertRaises(ValueError):
            evaluate_fomo_outcome(0, [1])


if __name__ == "__main__":
    unittest.main()
