import unittest
from mi_core.monte_carlo import anti_overfitting_score, monte_carlo_bootstrap

class MonteCarloTests(unittest.TestCase):
    def test_reproducible_bootstrap(self):
        returns = [0.02,-0.01,0.015,-0.005,0.01]
        a = monte_carlo_bootstrap(returns, simulations=200, seed=7)
        b = monte_carlo_bootstrap(returns, simulations=200, seed=7)
        self.assertEqual(a, b)
        self.assertGreaterEqual(a.p95_max_drawdown, 0.0)

    def test_validation_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError): monte_carlo_bootstrap([], simulations=200)
        with self.assertRaises(ValueError): monte_carlo_bootstrap([0.1], simulations=99)
        with self.assertRaises(ValueError): monte_carlo_bootstrap([-1.0], simulations=200)

    def test_anti_overfitting_flags_generalization(self):
        result = anti_overfitting_score(train_return=.40,oos_return=.12,oos_positive_rate=.60,oos_probability_of_loss=.30)
        self.assertTrue(result["oos_positive"])
        self.assertTrue(result["oos_positive_rate_pass"])
        self.assertTrue(result["loss_probability_pass"])
        self.assertGreater(result["score"], 0.0)

    def test_anti_overfitting_rejects_bad_ranges(self):
        with self.assertRaises(ValueError):
            anti_overfitting_score(train_return=1,oos_return=1,oos_positive_rate=1.2,oos_probability_of_loss=.2)

if __name__ == "__main__":
    unittest.main()
