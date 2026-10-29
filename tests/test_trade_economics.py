import unittest
from mi_core.trade_economics import evaluate_capital_target


class CapitalEconomicsTests(unittest.TestCase):
    def test_one_percent_move_passes_base_policy_minimum(self):
        r = evaluate_capital_target(1.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.15)
        self.assertAlmostEqual(r.modeled_profit_usd, 4.25)

    def test_strict_policy_is_independent_not_stacked(self):
        r = evaluate_capital_target(1.0, strict_cost=True)
        self.assertEqual(r.round_trip_cost_pct, 0.45)
        self.assertAlmostEqual(r.modeled_profit_usd, 2.75)
        self.assertFalse(r.approved)

    def test_component_model_is_explicit_alternative(self):
        r = evaluate_capital_target(1.0, cost_model="components")
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.35)

    def test_one_point_two_percent_move_is_acceptable_watch(self):
        r = evaluate_capital_target(1.2)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertGreaterEqual(r.modeled_profit_usd, 4.0)
        self.assertLess(r.modeled_profit_usd, 10.0)

    def test_twelve_percent_move_is_strong(self):
        r = evaluate_capital_target(12.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "STRONG")
        self.assertGreaterEqual(r.modeled_profit_usd, 10.0)

    def test_maker_fee_is_lower_than_taker_fee(self):
        taker = evaluate_capital_target(11.0, order_type="taker", cost_model="components")
        maker = evaluate_capital_target(11.0, order_type="maker", cost_model="components")
        self.assertLess(maker.round_trip_cost_pct, taker.round_trip_cost_pct)


if __name__ == "__main__":
    unittest.main()
