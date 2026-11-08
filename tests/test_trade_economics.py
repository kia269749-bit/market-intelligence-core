import unittest
from mi_core.trade_economics import evaluate_capital_target


class CapitalEconomicsTests(unittest.TestCase):
    def test_one_percent_move_passes_base_cost_minimum_floor(self):
        r = evaluate_capital_target(1.0)
        self.assertTrue(r.approved)
        self.assertEqual(r.tier, "WATCH")
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.15)
        self.assertGreaterEqual(r.modeled_profit_usd, 4.0)

    def test_strict_cost_mode_is_centralized(self):
        r = evaluate_capital_target(1.0, cost_mode="strict")
        self.assertFalse(r.approved)
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.45)
        self.assertAlmostEqual(r.required_move_pct, 1.25)

    def test_explicit_scenario_override_is_supported(self):
        r = evaluate_capital_target(1.2, round_trip_cost_pct=0.35)
        self.assertAlmostEqual(r.round_trip_cost_pct, 0.35)
        self.assertEqual(r.tier, "WATCH")

    def test_exchange_profile_is_explicit_legacy_sensitivity(self):
        taker = evaluate_capital_target(1.2, cost_mode="exchange_profile", order_type="taker")
        maker = evaluate_capital_target(1.2, cost_mode="exchange_profile", order_type="maker")
        self.assertLess(maker.round_trip_cost_pct, taker.round_trip_cost_pct)
        self.assertAlmostEqual(taker.round_trip_cost_pct, 0.35)


if __name__ == "__main__":
    unittest.main()
