import unittest

from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.project60_flow_adapter import evaluate_project60_flow


class Project60FlowBrainTests(unittest.TestCase):
    def test_fresh_project60_orderbook_and_trade_imbalance_vote_independently(self):
        snapshot = MarketSnapshot("BTCUSDT", 1_000_000, "1m", {
            "project60_timestamp_ms": 999_000,
            "project60_assets": {
                "BTC": {
                    "available": True,
                    "orderbook_imbalance_pct": 25.0,
                    "trade_imbalance_pct": 55.0,
                }
            },
        })
        rows = evaluate_project60_flow(snapshot)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.direction == "LONG" for row in rows))
        self.assertEqual({row.brain_id for row in rows}, {
            "market.project60_orderbook_imbalance",
            "market.project60_trade_flow",
        })

    def test_stale_or_missing_project60_data_cannot_vote(self):
        snapshot = MarketSnapshot("BTCUSDT", 1_000_000, "1m", {
            "project60_timestamp_ms": 100,
            "project60_assets": {
                "BTC": {"available": True, "orderbook_imbalance_pct": 40, "trade_imbalance_pct": 60}
            },
        })
        rows = evaluate_project60_flow(snapshot)
        self.assertTrue(all(not row.available and row.direction == "NO_TRADE" for row in rows))

    def test_future_project60_snapshot_cannot_vote(self):
        snapshot = MarketSnapshot("BTCUSDT", 1_000_000, "1m", {
            "project60_timestamp_ms": 1_000_001,
            "project60_assets": {
                "BTC": {"available": True, "orderbook_imbalance_pct": 40, "trade_imbalance_pct": 60}
            },
        })
        rows = evaluate_project60_flow(snapshot)
        self.assertTrue(all(not row.available for row in rows))


if __name__ == "__main__":
    unittest.main()
