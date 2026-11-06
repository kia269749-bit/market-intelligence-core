import unittest

from mi_core.strategy_ensemble import evaluate_consensus


def engine(direction, edge=0.2, oos="PASS", confidence=0.7):
    return {
        "available": True,
        "direction": direction,
        "confidence": confidence,
        "expected_net_edge_pct": edge,
        "oos_status": oos,
    }


class StrategyEnsembleTests(unittest.TestCase):
    def test_three_agreeing_positive_oos_engines_approve_shadow_only(self):
        result = evaluate_consensus({
            "institutional_flow": engine("BULLISH"),
            "trend_momentum": engine("BULLISH", edge=0.1),
            "smart_money_fomo": engine("BULLISH", edge=0.3),
        })
        self.assertEqual(result["direction"], "BULLISH")
        self.assertTrue(result["unanimous"])
        self.assertTrue(result["research_candidate"])
        self.assertTrue(result["approved_for_shadow"])
        self.assertFalse(result["actionable"])
        self.assertFalse(result["live_orders"])

    def test_directional_agreement_without_positive_edge_is_not_candidate(self):
        result = evaluate_consensus({
            "institutional_flow": engine("BEARISH", edge=0.2),
            "trend_momentum": engine("BEARISH", edge=0.0),
            "smart_money_fomo": engine("BEARISH", edge=0.3),
        })
        self.assertTrue(result["unanimous"])
        self.assertFalse(result["research_candidate"])
        self.assertIn("net_edge_not_positive_or_unavailable_for_every_engine", result["reasons"])

    def test_missing_or_conflicting_engine_never_passes(self):
        result = evaluate_consensus({
            "institutional_flow": engine("BULLISH"),
            "trend_momentum": engine("BEARISH"),
        })
        self.assertFalse(result["unanimous"])
        self.assertFalse(result["research_candidate"])
        self.assertFalse(result["approved_for_shadow"])
        self.assertIn("missing_or_invalid_engine_vote", result["reasons"])

    def test_positive_edge_without_oos_validation_does_not_approve_shadow(self):
        result = evaluate_consensus({
            "institutional_flow": engine("BULLISH", oos="UNVALIDATED"),
            "trend_momentum": engine("BULLISH"),
            "smart_money_fomo": engine("BULLISH"),
        })
        self.assertTrue(result["research_candidate"])
        self.assertFalse(result["approved_for_shadow"])


if __name__ == "__main__":
    unittest.main()
