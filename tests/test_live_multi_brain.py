import unittest
from unittest.mock import patch

from mi_core.live_brain import run_once


def feed(now_ms, bullish=True):
    if bullish:
        bids, asks, rate = [[100.0, 20.0]], [[100.1, 5.0]], -0.0008
    else:
        bids, asks, rate = [[100.0, 5.0]], [[100.1, 20.0]], 0.0008
    return {
        "orderbook": {"timestamp_ms": now_ms - 1000, "bids": bids, "asks": asks},
        "funding_events": [{"timestamp_ms": now_ms - 1000, "funding_rate": rate}],
        "open_interest": None,
    }


class LiveMultiBrainIntegrationTests(unittest.TestCase):
    def test_run_once_evaluates_and_reports_independent_asset_brains(self):
        now_seconds = 10_000
        now_ms = now_seconds * 1000
        market = {
            "rows": [{"symbol": "BTCUSDT", "price": 100.0, "change_24h_pct": 1.0}],
            "data_quality": {"status": "HEALTHY", "score": 1.0},
        }
        fomo = {"ts": now_seconds, "candidates": [], "research_only": True, "wallet_level": False}
        feeds = {"by_symbol": {
            "BTC": feed(now_ms, bullish=True),
            "ETH": feed(now_ms, bullish=False),
        }}
        with patch("mi_core.live_brain.time.time", return_value=now_seconds), \
             patch("mi_core.live_brain.fetch_snapshot", return_value=market), \
             patch("mi_core.live_brain.scan_boosted", return_value=fomo):
            report = run_once(
                symbols=["BTCUSDT", "ETHUSDT"],
                exchanges=[],
                brain_market_data=feeds,
            )
        self.assertEqual(set(report["multi_brains"]), {"BTCUSDT", "ETHUSDT"})
        self.assertEqual(report["multi_brains"]["BTCUSDT"]["central_decision"], "LONG")
        self.assertEqual(report["multi_brains"]["ETHUSDT"]["central_decision"], "SHORT")
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])


if __name__ == "__main__":
    unittest.main()
