import unittest
from mi_core.trade_economics import evaluate_capital_target


class CapitalEconomicsTests(unittest.TestCase):
    def test_nine_tenths_percent_move_is_below_floor_after_costs(self):
        r = evaluate_capital_target(0.9)
        self.assertFalse(r.approved)
        self.assertEqual(r.tier, "REJECT")
        self.assertLess(r.modeled_profit_usd, 4.0)

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

    def test_non_finite_expected_moves_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                result = evaluate_capital_target(value)
                self.assertFalse(result.approved)
                self.assertEqual(result.reason, "invalid_input")

    def test_invalid_spread_and_slippage_are_rejected(self):
        for kwargs in (
            {"spread_bps": float("nan")},
            {"slippage_bps": float("inf")},
            {"spread_bps": -1.0},
            {"slippage_bps": -1.0},
        ):
            with self.subTest(kwargs=kwargs):
                result = evaluate_capital_target(12.0, **kwargs)
                self.assertFalse(result.approved)
                self.assertEqual(result.reason, "invalid_input")

    def test_non_finite_capital_is_rejected(self):
        result = evaluate_capital_target(12.0, capital_usd=float("inf"))
        self.assertFalse(result.approved)
        self.assertEqual(result.reason, "invalid_input")

    def test_maker_fee_is_lower_than_taker_fee(self):
        taker = evaluate_capital_target(11.0, order_type="taker")
        maker = evaluate_capital_target(11.0, order_type="maker")
        self.assertLess(maker.round_trip_cost_pct, taker.round_trip_cost_pct)


if __name__ == "__main__":
    unittest.main()
