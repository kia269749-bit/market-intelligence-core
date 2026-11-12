import unittest

from mi_core.cost_policy import DEFAULT_COST_POLICY, get_round_trip_cost_pct
from mi_core.economic_edge import diagnose_economic_edge
from mi_core.profitability_gate import evaluate_setup
from mi_core.real_validation import _directional_metrics
from mi_core.trade_economics import evaluate_capital_target
from mi_core.validated_forecast import score_capital_targets


class CentralCostPolicyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.result = {"horizon_bars": 1, "predictions": [
            {"ts": 0, "pred": 1, "actual": 1, "actual_return_pct": 1.0,
             "p_up": 0.8, "p_flat": 0.1, "p_down": 0.1,
             "favorable_mfe_pct": 1.0, "adverse_mae_pct": 0.1}
        ]}

    def test_policy_rates_are_single_named_values(self):
        self.assertEqual(get_round_trip_cost_pct("base"), 0.15)
        self.assertEqual(get_round_trip_cost_pct("strict"), 0.15)
        self.assertEqual(DEFAULT_COST_POLICY.version, "v5-taker-0.15")

    def test_same_trade_uses_one_taker_cost_in_all_research_paths(self):
        for mode in ("base", "strict"):
            expected_cost, expected_net = 0.15, 4.25
            capital = evaluate_capital_target(1.0, cost_mode=mode)
            gate = evaluate_setup(100.0, 99.0, 102.0, "BULLISH", 0.9, cost_mode=mode)
            directional = _directional_metrics(self.result, cost_mode=mode)
            edge = diagnose_economic_edge(self.result, cost_mode=mode)
            scored = score_capital_targets(self.result, cost_mode=mode)

            self.assertAlmostEqual(capital.round_trip_cost_pct, expected_cost)
            self.assertAlmostEqual(gate.round_trip_cost_pct, expected_cost)
            self.assertAlmostEqual(directional["net_profit_usd"], expected_net)
            self.assertAlmostEqual(edge["thresholds"]["round_trip_cost_pct"], expected_cost)
            self.assertAlmostEqual(scored["round_trip_cost_pct"], expected_cost)

    def test_retired_component_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "component cost mode is retired"):
            evaluate_capital_target(1.0, cost_model="components")


if __name__ == "__main__":
    unittest.main()
