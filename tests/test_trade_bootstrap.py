import unittest

from mi_core.trade_bootstrap import run_trade_bootstrap


class TradeBootstrapTests(unittest.TestCase):
    def test_is_deterministic_and_marks_research_only(self):
        trades = [
            {"net_pnl_usd": 8.0},
            {"net_pnl_usd": -5.0},
            {"net_pnl_usd": 4.0},
            {"net_pnl_usd": -2.0},
            {"net_pnl_usd": 7.0},
        ]
        first = run_trade_bootstrap(trades, simulations=500, block_size=2, seed=19)
        second = run_trade_bootstrap(trades, simulations=500, block_size=2, seed=19)
        self.assertEqual(first, second)
        self.assertEqual(first["trade_count"], 5)
        self.assertEqual(first["block_size"], 2)
        self.assertTrue(first["research_only"])
        self.assertFalse(first["live_orders"])
        self.assertIn("net_pnl_p05_usd", first)
        self.assertIn("max_drawdown_p95_usd", first)

    def test_all_positive_outcomes_have_positive_bootstrap_total(self):
        result = run_trade_bootstrap([1, 2, 3, 4], simulations=100, seed=1)
        self.assertEqual(result["probability_positive_net_pct"], 100.0)
        self.assertGreater(result["expectancy_ci95_low_usd"], 0)
        self.assertEqual(result["max_drawdown_p95_usd"], 0.0)

    def test_accepts_realized_net_pnl_from_trade_records(self):
        result = run_trade_bootstrap(
            [{"gross_pnl_usd": 10.0, "cost_usd": 4.0, "net_pnl_usd": 6.0}],
            simulations=100,
        )
        self.assertAlmostEqual(result["observed_net_pnl_usd"], 6.0)
        self.assertAlmostEqual(result["observed_expectancy_usd"], 6.0)

    def test_rejects_empty_or_non_finite_outcomes(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            run_trade_bootstrap([], simulations=100)
        with self.assertRaisesRegex(ValueError, "finite"):
            run_trade_bootstrap([1.0, float("nan")], simulations=100)

    def test_rejects_invalid_simulation_and_block_settings(self):
        with self.assertRaisesRegex(ValueError, "simulations"):
            run_trade_bootstrap([1.0, -1.0], simulations=99)
        with self.assertRaisesRegex(ValueError, "block_size"):
            run_trade_bootstrap([1.0, -1.0], simulations=100, block_size=3)

    def test_initial_equity_validation_is_fail_closed(self):
        for value in (True, float("nan"), float("inf"), "not-a-number"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "initial_equity_usd"):
                run_trade_bootstrap([1.0, -1.0], simulations=100, initial_equity_usd=value)
        result = run_trade_bootstrap([1.0, -1.0], simulations=100, initial_equity_usd="500")
        self.assertGreaterEqual(result["max_drawdown_p95_pct_initial_equity"], 0.2)


if __name__ == "__main__":
    unittest.main()
