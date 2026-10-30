import math
import unittest

from mi_core.costs import (
    BASE_ROUND_TRIP_COST_PCT,
    STRICT_ROUND_TRIP_COST_PCT,
    ExecutionCostConfig,
    apply_cost_to_gross_pnl,
    estimate_execution_cost,
    get_round_trip_cost_pct,
)
from mi_core.platform_core import (
    CostModel,
    OrderIntent,
    PlatformConfig,
    PortfolioState,
    Position,
)


class CentralCostTests(unittest.TestCase):
    def test_local_research_policy_is_preserved(self):
        self.assertEqual(BASE_ROUND_TRIP_COST_PCT, 0.15)
        self.assertEqual(STRICT_ROUND_TRIP_COST_PCT, 0.45)
        self.assertEqual(get_round_trip_cost_pct("base"), 0.15)
        self.assertEqual(get_round_trip_cost_pct("strict"), 0.45)

    def test_research_policy_cost_is_applied_once(self):
        self.assertAlmostEqual(CostModel.research("base").cost_usd(500), 0.75)
        self.assertAlmostEqual(CostModel.research("strict").cost_usd(500), 2.25)

    def test_execution_components_are_separate_and_round_trip_once(self):
        cost = estimate_execution_cost(500)
        self.assertAlmostEqual(cost.total, 0.55)
        self.assertAlmostEqual(CostModel.execution().cost_usd(500), 0.55)

    def test_cost_modes_cannot_be_stacked(self):
        with self.assertRaises(ValueError):
            CostModel(
                mode="execution_components",
                policy="base",
                execution_config=ExecutionCostConfig(),
            )
        with self.assertRaises(ValueError):
            CostModel(mode="research_policy", policy="strict",
                      execution_config=ExecutionCostConfig())

    def test_cost_config_rejects_bool_nan_and_infinity(self):
        for bad in (True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    ExecutionCostConfig(taker_fee_bps=bad)

    def test_estimator_rejects_invalid_numbers(self):
        for bad in (True, float("nan"), float("inf"), 0, -1):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    estimate_execution_cost(bad)
        with self.assertRaises(ValueError):
            estimate_execution_cost(100, fee_bps=float("nan"))

    def test_gross_loss_is_supported_and_cost_is_subtracted(self):
        cost = estimate_execution_cost(100)
        self.assertAlmostEqual(apply_cost_to_gross_pnl(-2.0, cost), -2.11)
        with self.assertRaises(ValueError):
            apply_cost_to_gross_pnl(float("nan"), cost)


class PortfolioTests(unittest.TestCase):
    def test_long_and_short_mark_to_market(self):
        state = PortfolioState(
            cash_usd=1000,
            positions=(
                Position("BTC", quantity=2, entry_price=100),
                Position("ETH", quantity=-3, entry_price=50),
            ),
        )
        # BTC: +20; ETH short: +15; equity = 1035.
        self.assertAlmostEqual(state.equity({"btc": 110, "ETH": 45}), 1035)

    def test_missing_and_extra_prices_fail_closed(self):
        state = PortfolioState(100, (Position("BTC", 1, 10),))
        with self.assertRaises(ValueError):
            state.equity({})
        with self.assertRaises(ValueError):
            state.equity({"BTC": 11, "ETH": 20})

    def test_bad_prices_and_duplicate_symbols_are_rejected(self):
        state = PortfolioState(100, (Position("BTC", 1, 10),))
        for bad in (True, float("nan"), float("inf"), 0, -1):
            with self.subTest(price=bad):
                with self.assertRaises(ValueError):
                    state.equity({"BTC": bad})
        with self.assertRaises(ValueError):
            PortfolioState(100, (Position("btc", 1, 10), Position("BTC", 2, 10)))


class SafetyAndIntentTests(unittest.TestCase):
    def test_platform_defaults_and_safety_are_locked(self):
        config = PlatformConfig()
        self.assertEqual(config.capital_usd, 500)
        self.assertEqual(config.min_profit_usd, 4)
        self.assertEqual(config.preferred_profit_usd, 10)
        self.assertTrue(config.research_only)
        self.assertFalse(config.live_orders)
        with self.assertRaises(TypeError):
            PlatformConfig(live_orders=True)

    def test_platform_economic_settings_are_validated(self):
        with self.assertRaises(ValueError):
            PlatformConfig(capital_usd=float("nan"))
        with self.assertRaises(ValueError):
            PlatformConfig(min_profit_usd=11, preferred_profit_usd=10)

    def test_market_and_limit_intents(self):
        market = OrderIntent("btc", "buy", 0.1)
        self.assertEqual(market.symbol, "BTC")
        limit = OrderIntent("eth", "sell", 1, "limit", 2500)
        self.assertEqual(limit.limit_price, 2500)
        with self.assertRaises(ValueError):
            OrderIntent("BTC", "buy", 1, "market", 100)
        with self.assertRaises(ValueError):
            OrderIntent("BTC", "buy", 1, "limit")
        with self.assertRaises(ValueError):
            OrderIntent("BTC", "buy", float("nan"))


if __name__ == "__main__":
    unittest.main()
