import unittest

from mi_core.costs import (
    ExecutionCostConfig,
    apply_cost_to_gross_pnl,
    estimate_execution_cost,
)


class ExecutionCostTests(unittest.TestCase):
    def test_default_components_are_explicit(self):
        cost = estimate_execution_cost(10_000.0)
        self.assertAlmostEqual(cost.fee, 5.0)
        self.assertAlmostEqual(cost.spread, 2.0)
        self.assertAlmostEqual(cost.slippage, 3.0)
        self.assertAlmostEqual(cost.impact, 1.0)
        self.assertAlmostEqual(cost.total, 11.0)

    def test_custom_assumptions(self):
        cfg = ExecutionCostConfig(
            taker_fee_bps=10,
            spread_bps=4,
            slippage_bps=6,
            impact_bps=2,
        )
        cost = estimate_execution_cost(5_000, config=cfg)
        self.assertAlmostEqual(cost.total, 11.0)

    def test_legacy_fee_override(self):
        cost = estimate_execution_cost(10_000, fee_bps=7, spread_bps=0, slippage_bps=0, impact_bps=0)
        self.assertAlmostEqual(cost.total, 7.0)

    def test_net_pnl(self):
        cost = estimate_execution_cost(10_000)
        self.assertAlmostEqual(apply_cost_to_gross_pnl(25.0, cost), 14.0)

    def test_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            estimate_execution_cost(0)
        with self.assertRaises(ValueError):
            ExecutionCostConfig(slippage_bps=-1)


if __name__ == "__main__":
    unittest.main()
