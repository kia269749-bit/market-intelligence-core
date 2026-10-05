import unittest

from mi_core.fomo_intelligence import analyze_fomo


class FomoIntelligenceTests(unittest.TestCase):
    def test_event_without_trader_history_is_not_research_flag(self):
        result = analyze_fomo(
            symbol="DOGE", timestamp=1,
            volume_history=[100, 105, 95, 100], current_volume=250,
        )
        self.assertIsNotNone(result.event)
        self.assertFalse(result.actionable_research_flag)

    def test_event_with_strong_trader_history_is_flagged(self):
        result = analyze_fomo(
            symbol="DOGE", timestamp=2,
            volume_history=[100, 105, 95, 100], current_volume=250,
            trader_metrics={
                "trader_id": "t1", "snapshots": 12,
                "historical_score": 1, "rank_score": 1,
                "pnl_positive_rate": 1, "sample_confidence": 1,
                "meme_edge": 1,
            },
        )
        self.assertTrue(result.actionable_research_flag)
        self.assertGreaterEqual(result.trader_confidence, 0.99)

    def test_no_market_event_means_no_flag(self):
        result = analyze_fomo(
            symbol="DOGE", timestamp=3,
            volume_history=[100, 105, 95, 100], current_volume=105,
            trader_metrics={
                "trader_id": "t1", "snapshots": 12,
                "historical_score": 1, "rank_score": 1,
                "pnl_positive_rate": 1, "sample_confidence": 1,
            },
        )
        self.assertIsNone(result.event)
        self.assertFalse(result.actionable_research_flag)


if __name__ == "__main__":
    unittest.main()
