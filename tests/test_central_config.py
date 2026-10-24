import unittest
from unittest.mock import patch

from mi_core.central_config import load_settings


class CentralConfigTests(unittest.TestCase):
    def test_single_source_is_lbank_futures_and_research_only(self):
        cfg = load_settings()
        self.assertEqual(cfg.exchange, "lbank")
        self.assertEqual(cfg.market, "futures")
        self.assertTrue(cfg.symbols)
        self.assertTrue(cfg.research_only)
        self.assertFalse(cfg.live_orders)

    def test_market_data_venue_is_separate_from_lbank_cost_model(self):
        cfg = load_settings()
        self.assertEqual(cfg.data_exchange, "hyperliquid")
        self.assertEqual(cfg.exchange, "lbank")
        self.assertEqual(cfg.market, "futures")

    def test_fee_source_is_explicit_about_account_verification(self):
        cfg = load_settings()
        self.assertGreaterEqual(cfg.taker_fee_bps, 0)
        self.assertGreaterEqual(cfg.maker_fee_bps, 0)
        self.assertTrue(cfg.fee_source)
        self.assertIsInstance(cfg.fee_account_verified, bool)

    def test_rejects_non_finite_fee_assumptions(self):
        defaults = {
            "fees": {"taker_bps": float("nan"), "maker_bps": 2.0, "source": "test"},
            "costs": {"spread_bps": 2.0, "slippage_bps": 3.0, "impact_bps": 1.0},
            "capital_policy": {"capital_usd": 500.0, "min_profit_usd": 4.0, "preferred_profit_usd": 10.0},
        }
        markets = {
            "primary_exchange": "lbank", "market_data_exchange": "hyperliquid",
            "market": "futures", "product_group": "SwapU", "symbols": ["BTCUSDT"],
            "research_only": True, "live_orders": False,
        }
        with patch("mi_core.central_config._read_json", side_effect=[defaults, markets]):
            with self.assertRaisesRegex(RuntimeError, "finite and non-negative"):
                load_settings()

    def test_rejects_non_finite_capital_policy(self):
        defaults = {
            "fees": {"taker_bps": 6.0, "maker_bps": 2.0, "source": "test"},
            "costs": {"spread_bps": 2.0, "slippage_bps": 3.0, "impact_bps": 1.0},
            "capital_policy": {"capital_usd": float("inf"), "min_profit_usd": 4.0, "preferred_profit_usd": 10.0},
        }
        markets = {
            "primary_exchange": "lbank", "market_data_exchange": "hyperliquid",
            "market": "futures", "product_group": "SwapU", "symbols": ["BTCUSDT"],
            "research_only": True, "live_orders": False,
        }
        with patch("mi_core.central_config._read_json", side_effect=[defaults, markets]):
            with self.assertRaisesRegex(RuntimeError, "capital targets must be finite"):
                load_settings()


if __name__ == "__main__":
    unittest.main()
