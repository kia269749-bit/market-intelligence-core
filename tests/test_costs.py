import unittest

from mi_core.costs import (
    ExecutionCostConfig,
    apply_cost_to_gross_pnl,
    estimate_execution_cost,
)


class ExecutionCostTests(unittest.TestCase):
    def test_default_components_are_explicit(self):
        cost = estimate_execution_cost(10_000.0)
        self.assertAlmostEqual(cost.fee, 12.0)
        self.assertAlmostEqual(cost.spread, 4.0)
        self.assertAlmostEqual(cost.slippage, 6.0)
        self.assertAlmostEqual(cost.impact, 2.0)
        self.assertAlmostEqual(cost.total, 24.0)

    def test_custom_assumptions(self):
        cfg = ExecutionCostConfig(
            taker_fee_bps=10,
            spread_bps=4,
            slippage_bps=6,
            impact_bps=2,
        )
        cost = estimate_execution_cost(5_000, config=cfg)
        self.assertAlmostEqual(cost.total, 22.0)

    def test_legacy_fee_override(self):
        cost = estimate_execution_cost(10_000, fee_bps=7, spread_bps=0, slippage_bps=0, impact_bps=0)
        self.assertAlmostEqual(cost.total, 14.0)

    def test_net_pnl(self):
        cost = estimate_execution_cost(10_000)
        self.assertAlmostEqual(apply_cost_to_gross_pnl(25.0, cost), 1.0)

    def test_rejects_invalid_values(self):
        for notional in (0, float("inf"), float("nan"), True):
            with self.subTest(notional=notional), self.assertRaises(ValueError):
                estimate_execution_cost(notional)
        for override in (float("nan"), True):
            with self.subTest(override=override), self.assertRaises(ValueError):
                estimate_execution_cost(1000, fee_bps=override)
        for kwargs in (
            {"slippage_bps": -1},
            {"taker_fee_bps": float("nan")},
            {"impact_bps": float("inf")},
            {"spread_bps": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ExecutionCostConfig(**kwargs)

    def test_numeric_string_costs_are_normalized(self):
        cfg = ExecutionCostConfig(
            taker_fee_bps="6", spread_bps="2",
            slippage_bps="3", impact_bps="1",
        )
        self.assertIsInstance(cfg.taker_fee_bps, float)
        self.assertAlmostEqual(estimate_execution_cost(10000, config=cfg).total, 24.0)

    def test_rejects_invalid_execution_cost_records_and_gross_pnl(self):
        with self.assertRaisesRegex(ValueError, "total"):
            from mi_core.costs import ExecutionCost
            ExecutionCost(notional=100, fee=1, spread=1, slippage=1, impact=1, total=float("nan"))
        cost = estimate_execution_cost(1000)
        for pnl in (float("nan"), float("inf"), True):
            with self.subTest(pnl=pnl), self.assertRaisesRegex(ValueError, "gross_pnl"):
                apply_cost_to_gross_pnl(pnl, cost)


if __name__ == "__main__":
    unittest.main()
