import unittest
from mi_core.profitability import ProfitabilityGateConfig, evaluate_profitability

class ProfitabilityTests(unittest.TestCase):
    def test_passes_when_all_gates_pass(self):
        result = evaluate_profitability(oos_return=.18, oos_drawdown=.12, oos_positive_rate=.62,
            monte_carlo_probability_of_loss=.31, monte_carlo_p05_return=-.04, trade_count=60)
        self.assertTrue(result.eligible)
        self.assertEqual(result.reasons, ())

    def test_rejects_weak_oos_and_small_sample(self):
        result = evaluate_profitability(oos_return=-.02, oos_drawdown=.25, oos_positive_rate=.44,
            monte_carlo_probability_of_loss=.61, monte_carlo_p05_return=-.16, trade_count=12)
        self.assertFalse(result.eligible)
        self.assertIn("oos_return", result.reasons)
        self.assertIn("oos_drawdown", result.reasons)
        self.assertIn("minimum_trades", result.reasons)

    def test_custom_thresholds(self):
        cfg = ProfitabilityGateConfig(min_oos_return=.05, max_oos_drawdown=.10,
            min_oos_positive_rate=.60, max_loss_probability=.35,
            min_monte_carlo_p05_return=-.03, min_trades=10)
        result = evaluate_profitability(oos_return=.06, oos_drawdown=.09, oos_positive_rate=.61,
            monte_carlo_probability_of_loss=.34, monte_carlo_p05_return=-.02, trade_count=10, config=cfg)
        self.assertTrue(result.eligible)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            evaluate_profitability(oos_return=.1, oos_drawdown=.1, oos_positive_rate=1.2,
                monte_carlo_probability_of_loss=.2, monte_carlo_p05_return=-.01, trade_count=30)
        with self.assertRaises(ValueError):
            evaluate_profitability(oos_return=.1, oos_drawdown=-.1, oos_positive_rate=.6,
                monte_carlo_probability_of_loss=.2, monte_carlo_p05_return=-.01, trade_count=30)

    def test_all_checks_are_explicit(self):
        result = evaluate_profitability(oos_return=.10, oos_drawdown=.10, oos_positive_rate=.60,
            monte_carlo_probability_of_loss=.40, monte_carlo_p05_return=-.05, trade_count=30)
        self.assertEqual(set(result.checks), {"oos_return", "oos_drawdown", "oos_positive_rate",
            "monte_carlo_loss_probability", "monte_carlo_p05_return", "minimum_trades"})

if __name__ == "__main__":
    unittest.main()
