import unittest
from mi_core.shadow_trading import ShadowSignal, ShadowOutcome, match_outcomes, summarize_outcomes

class ShadowTradingTests(unittest.TestCase):
    def signals(self):
        return [
            ShadowSignal("s1", 100, "BTCUSDT", "LONG", 100.0, .8, "TREND"),
            ShadowSignal("s2", 200, "ETHUSDT", "SHORT", 200.0, .7, "RANGE"),
        ]

    def test_match_and_summary(self):
        matches = match_outcomes(self.signals(), [
            ShadowOutcome("s1", 110, 105.0, .05, .08, -.02),
            ShadowOutcome("s2", 210, 190.0, .05, .06, -.01),
        ])
        summary = summarize_outcomes(matches)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["win_rate"], 1.0)
        self.assertAlmostEqual(summary["mean_return"], .05)

    def test_rejects_unknown_or_early_outcome(self):
        with self.assertRaises(ValueError):
            match_outcomes(self.signals(), [ShadowOutcome("missing", 210, 1.0, .1)])
        with self.assertRaises(ValueError):
            match_outcomes(self.signals(), [ShadowOutcome("s1", 100, 101.0, .01)])

    def test_rejects_duplicate_signal(self):
        signals = self.signals() + [self.signals()[0]]
        with self.assertRaises(ValueError):
            match_outcomes(signals, [])

if __name__ == "__main__":
    unittest.main()
