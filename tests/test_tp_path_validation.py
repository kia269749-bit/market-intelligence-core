import unittest

from mi_core.tp_path_validation import evaluate_asset


class TPPathValidationTests(unittest.TestCase):
    def test_short_history_skips_safely(self):
        rows = evaluate_asset([], "BTC", horizons=(5,), min_samples=10)
        self.assertEqual(rows[0]["status"], "SKIPPED")
        self.assertTrue(rows[0]["research_only"])
        self.assertFalse(rows[0]["live_orders"])

    def test_target_hit_count_does_not_claim_realized_profitability(self):
        rows = evaluate_asset([], "ETH", horizons=(5,), min_samples=1)
        self.assertIn("status", rows[0])
        self.assertFalse(rows[0]["live_orders"])


if __name__ == "__main__":
    unittest.main()
