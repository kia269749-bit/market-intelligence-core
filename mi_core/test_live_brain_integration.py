"""Regression probe for the multi-brain live coordinator.

This duplicates the existing public integration fixture inside mi_core so the
failure details are surfaced before the broader legacy suite runs.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from mi_core.live_brain import run_once


def _feed(now_ms: int, bullish: bool = True) -> dict:
    if bullish:
        bids, asks, rate = [[100.0, 20.0]], [[100.1, 5.0]], -0.0008
    else:
        bids, asks, rate = [[100.0, 5.0]], [[100.1, 20.0]], 0.0008
    return {
        "orderbook": {"timestamp_ms": now_ms - 1000, "bids": bids, "asks": asks},
        "funding_events": [{"timestamp_ms": now_ms - 1000, "funding_rate": rate}],
        "open_interest": None,
    }


class LiveBrainIntegrationProbeTests(unittest.TestCase):

    def test_evaluate_brains_directly_surfaces_runtime_exception(self):
        from mi_core.brains.contracts import MarketSnapshot
        from mi_core.brains.engine import evaluate_brains
        now_ms = 10_000_000
        snapshot = MarketSnapshot(
            "BTCUSDT",
            now_ms,
            "1h",
            {
                "orderbook": {"timestamp_ms": now_ms - 1000,
                              "bids": [[100.0, 20.0]], "asks": [[100.1, 5.0]]},
                "funding_events": [{"timestamp_ms": now_ms - 1000, "funding_rate": -0.0008}],
                "open_interest": None,
            },
        )
        report = evaluate_brains(snapshot)
        self.assertTrue(report.research_only)
        self.assertFalse(report.live_orders)

    def test_multi_brain_report_contains_decisions(self):
        now_seconds = 10_000
        now_ms = now_seconds * 1000
        market = {
            "rows": [{"symbol": "BTCUSDT", "price": 100.0, "change_24h_pct": 1.0}],
            "data_quality": {"status": "HEALTHY", "score": 1.0},
        }
        fomo = {"ts": now_seconds, "candidates": [], "research_only": True, "wallet_level": False}
        feeds = {"by_symbol": {
            "BTC": _feed(now_ms, bullish=True),
            "ETH": _feed(now_ms, bullish=False),
        }}
        with patch("mi_core.live_brain.time.time", return_value=now_seconds), \
             patch("mi_core.live_brain.fetch_snapshot", return_value=market), \
             patch("mi_core.live_brain.scan_boosted", return_value=fomo):
            report = run_once(
                symbols=["BTCUSDT", "ETHUSDT"],
                exchanges=[],
                brain_market_data=feeds,
            )
        btc = report["multi_brains"]["BTCUSDT"]
        self.assertIn("central_decision", btc, btc)
        eth = report["multi_brains"]["ETHUSDT"]
        self.assertIn("central_decision", eth, eth)
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])


if __name__ == "__main__":
    unittest.main()
