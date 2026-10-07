import unittest

from mi_core.opportunity_score import score_opportunity


class OpportunityScoreTests(unittest.TestCase):
    def _base(self):
        return {
            "forecast": {"direction": "UP", "confidence": 0.92, "expected_return_pct": 0.55},
            "ranking": {"score": 0.80},
            "adaptive_context": {"regime": "MIXED", "quality_score": 1.0, "agreement": 0.85},
            "trade_filter": {
                "policy_status": "STRONG",
                "reason": "expected_move_below_usd4_after_costs",
                "net_move_pct": 0.20,
            },
        }

    def test_strong_setup_becomes_early_watch(self):
        result = score_opportunity(**self._base())
        self.assertTrue(result["early_watch"])
        self.assertEqual(result["label"], "EARLY_WATCH")
        self.assertGreaterEqual(result["score"], 65.0)

    def test_early_watch_is_research_only(self):
        result = score_opportunity(**self._base())
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_negative_edge_is_not_early_watch(self):
        data = self._base()
        data["trade_filter"]["net_move_pct"] = -0.01
        result = score_opportunity(**data)
        self.assertFalse(result["early_watch"])

    def test_conflicting_sources_are_not_early_watch(self):
        data = self._base()
        data["adaptive_context"]["agreement"] = 0.50
        result = score_opportunity(**data)
        self.assertFalse(result["early_watch"])

    def test_nondirectional_is_not_opportunity(self):
        data = self._base()
        data["forecast"]["direction"] = "FLAT"
        result = score_opportunity(**data)
        self.assertEqual(result["label"], "NONE")


if __name__ == "__main__":
    unittest.main()
