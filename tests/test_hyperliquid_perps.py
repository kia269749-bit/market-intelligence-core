import unittest
from unittest.mock import patch

from mi_core.hyperliquid_perps import fetch_orderbook, fetch_snapshot


class HyperliquidPerpsTests(unittest.TestCase):
    @patch("mi_core.hyperliquid_perps._post")
    def test_snapshot_parses_perp_contexts_and_tags_lbank_cost_model(self, post):
        post.return_value = [
            {"universe": [{"name": "BTC"}, {"name": "ETH"}]},
            [
                {"markPx": "65000", "prevDayPx": "64000", "openInterest": "1200", "funding": "0.0001"},
                {"markPx": "3200", "prevDayPx": "3300", "openInterest": "900", "funding": "-0.0002"},
            ],
        ]
        result = fetch_snapshot(["BTCUSDT", "ETHUSDT"])
        self.assertEqual(result["exchange"], "hyperliquid")
        self.assertEqual(result["market"], "perpetuals")
        self.assertEqual(result["cost_model_exchange"], "lbank")
        self.assertEqual(result["cost_model_market"], "futures")
        self.assertEqual(result["data_quality"]["status"], "HEALTHY")
        self.assertEqual(result["rows"][0]["price"], 65000.0)
        self.assertAlmostEqual(result["rows"][0]["change_24h_pct"], (65000 / 64000 - 1) * 100)
        self.assertEqual(result["rows"][1]["funding_rate"], -0.0002)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        post.assert_called_once_with({"type": "metaAndAssetCtxs"}, timeout=8)

    @patch("mi_core.hyperliquid_perps._post")
    def test_orderbook_parses_public_l2_levels(self, post):
        post.return_value = {
            "time": 1791257623000,
            "levels": [
                [{"px": "100", "sz": "2", "n": 3}],
                [{"px": "101", "sz": "4", "n": 2}],
            ],
        }
        result = fetch_orderbook("BTCUSDT", depth=5)
        self.assertEqual(result["exchange"], "hyperliquid")
        self.assertEqual(result["symbol"], "BTC")
        self.assertEqual(result["best_bid"], 100.0)
        self.assertEqual(result["best_ask"], 101.0)
        self.assertEqual(result["cost_model_exchange"], "lbank")
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])

    def test_orderbook_depth_is_bounded(self):
        with self.assertRaises(ValueError):
            fetch_orderbook("BTCUSDT", depth=21)


if __name__ == "__main__":
    unittest.main()
