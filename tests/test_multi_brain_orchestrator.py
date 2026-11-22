import unittest

from mi_core.brains.contracts import BrainProposal, MarketSnapshot
from mi_core.brains.orchestrator import arbitrate


def proposal(brain, family, direction, ts=100_000, confidence=0.8):
    return BrainProposal(brain, family, direction, confidence, ts, (brain,), ("test",))


class MultiBrainOrchestratorTests(unittest.TestCase):
    def test_two_independent_families_can_signal_long(self):
        result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [
            proposal("ta", "technical", "LONG"),
            proposal("flow", "orderflow", "LONG"),
        ])
        self.assertEqual(result.decision, "LONG")
        self.assertFalse(result.live_orders)

    def test_same_family_duplicates_count_once(self):
        result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [
            proposal("rsi", "technical", "LONG"),
            proposal("macd", "technical", "LONG"),
        ])
        self.assertEqual(result.decision, "NO_TRADE")
        self.assertIn("insufficient_independent_brain_families", result.reasons)

    def test_stale_or_future_proposals_are_ignored(self):
        result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [
            proposal("ta", "technical", "LONG", 1),
            proposal("flow", "orderflow", "LONG", 100_001),
        ])
        self.assertEqual(result.decision, "NO_TRADE")

    def test_win_rate_is_shrunk_for_small_samples(self):
        stats = {"ta": {"wins": 1, "losses": 0}, "flow": {"wins": 1, "losses": 0}}
        result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [
            proposal("ta", "technical", "LONG"),
            proposal("flow", "orderflow", "LONG"),
        ], stats)
        self.assertEqual(result.decision, "LONG")
        self.assertTrue(all(v["performance_weight"] < 1.0 for v in result.votes))


if __name__ == "__main__":
    unittest.main()
