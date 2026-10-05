import unittest

from mi_core.fomo_trader_confidence import attach_trader_confidence, trader_confidence


class FomoTraderConfidenceTests(unittest.TestCase):
    def test_insufficient_history_is_not_eligible(self):
        result = trader_confidence({
            "trader_id": "a", "snapshots": 2, "historical_score": 1,
            "rank_score": 1, "pnl_positive_rate": 1, "sample_confidence": 1,
        })
        self.assertFalse(result.eligible)

    def test_strong_history_can_be_eligible(self):
        result = trader_confidence({
            "trader_id": "a", "snapshots": 12, "historical_score": 1,
            "rank_score": 1, "pnl_positive_rate": 1, "sample_confidence": 1,
            "meme_edge": 1,
        })
        self.assertTrue(result.eligible)
        self.assertGreaterEqual(result.confidence, 0.99)

    def test_low_quality_is_not_eligible(self):
        result = trader_confidence({
            "trader_id": "a", "snapshots": 12, "historical_score": 0.2,
            "rank_score": 0.2, "pnl_positive_rate": 0.2, "sample_confidence": 1,
        })
        self.assertFalse(result.eligible)

    def test_attach_sorts_by_confidence(self):
        rows = attach_trader_confidence([
            {"trader_id": "weak", "snapshots": 3, "historical_score": 0.2,
             "rank_score": 0.2, "pnl_positive_rate": 0.2, "sample_confidence": 0.3},
            {"trader_id": "strong", "snapshots": 12, "historical_score": 0.9,
             "rank_score": 0.9, "pnl_positive_rate": 0.9, "sample_confidence": 1,
             "meme_edge": 0.8},
        ])
        self.assertEqual(rows[0]["trader_id"], "strong")


if __name__ == "__main__":
    unittest.main()
