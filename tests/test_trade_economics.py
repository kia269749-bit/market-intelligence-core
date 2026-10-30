import unittest
from mi_core.trade_economics import evaluate_capital_target


class CapitalEconomicsTests(unittest.TestCase):
    def test_base_cost_manual_calculation(self):
        # $500 * (1.00% - 0.15%) = $4.25 net.
        r = evaluate_capital_target(1.0, cost_policy="base")
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.15)
        self.assertAlmostEqual(r.modeled_profit_usd, 4.25)

    def test_strict_cost_manual_calculation(self):
        # $500 * (1.00% - 0.45%) = $2.75 net.
        r = evaluate_capital_target(1.0, cost_policy="strict")
        self.assertFalse(r.approved)
        self.assertEqual(r.tier, "REJECT")
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.45)
        self.assertAlmostEqual(r.modeled_profit_usd, 2.75)

    def test_explicit_override_is_exclusive(self):
        r = evaluate_capital_target(1.2, round_trip_cost_pct=0.35)
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.35)
        self.assertAlmostEqual(r.modeled_profit_usd, 4.25)

    def test_unknown_policy_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate_capital_target(1.2, cost_policy="hyperliquid_perps")

    def test_invalid_inputs_rejected(self):
        for value in (True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate_capital_target(value)
        with self.assertRaises(ValueError):
            evaluate_capital_target(1.0, capital_usd=-1)
        with self.assertRaises(ValueError):
            evaluate_capital_target(1.0, min_profit_usd=-1)
        with self.assertRaises(ValueError):
            evaluate_capital_target(1.0, min_profit_usd=10, preferred_profit_usd=4)


if __name__ == "__main__":
    unittest.main()
