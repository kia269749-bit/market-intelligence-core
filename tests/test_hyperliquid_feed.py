import unittest
from unittest.mock import patch

from mi_core.brains import hyperliquid_feed


class HyperliquidFeedTests(unittest.TestCase):
    def setUp(self):
        hyperliquid_feed._CACHE.clear()
        hyperliquid_feed._OI_PREVIOUS.clear()

    def test_read_only_feed_parses_book_and_latest_settled_funding(self):
        now = 1_000_000
        responses = [
            {"time": now, "levels": [
                [{"px": "100", "sz": "5"}],
                [{"px": "101", "sz": "3"}],
            ]},
            [
                {"time": now - 10_000, "fundingRate": "0.0001"},
                {"time": now + 1, "fundingRate": "0.0009"},
            ],
            [{"universe": [{"name": "BTC"}]}, [{"openInterest": "1000", "markPx": "100"}]],
        ]
        with patch.object(hyperliquid_feed, "_post", side_effect=responses):
            result = hyperliquid_feed.fetch_hyperliquid_brain_context("BTC", now_ms=now, force=True)
        self.assertEqual(result["orderbook"]["bids"], [[100.0, 5.0]])
        self.assertEqual(result["funding_events"], [{"timestamp_ms": now - 10_000, "funding_rate": 0.0001}])
        self.assertIsNone(result["open_interest"])

    def test_open_interest_change_requires_two_observations(self):
        now = 2_000_000
        response_a = [{"universe": [{"name": "BTC"}]}, [{"openInterest": "1000", "markPx": "100"}]]
        response_b = [{"universe": [{"name": "BTC"}]}, [{"openInterest": "1010", "markPx": "101"}]]
        with patch.object(hyperliquid_feed, "_post", side_effect=[
            {"time": now, "levels": [[{"px": "100", "sz": "1"}], [{"px": "101", "sz": "1"}]]},
            [], response_a,
        ]):
            first = hyperliquid_feed.fetch_hyperliquid_brain_context("BTC", now_ms=now, force=True)
        self.assertIsNone(first["open_interest"])
        with patch.object(hyperliquid_feed, "_post", side_effect=[
            {"time": now + 30_000, "levels": [[{"px": "100", "sz": "1"}], [{"px": "101", "sz": "1"}]]},
            [], response_b,
        ]):
            second = hyperliquid_feed.fetch_hyperliquid_brain_context("BTC", now_ms=now + 30_000, force=True)
        self.assertAlmostEqual(second["open_interest"]["change_pct"], 1.0)
        self.assertAlmostEqual(second["open_interest"]["price_change_pct"], 1.0)


if __name__ == "__main__":
    unittest.main()
