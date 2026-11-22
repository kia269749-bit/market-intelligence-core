import unittest

from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.derivatives_adapter import evaluate_derivatives_specialists
from mi_core.brains.orderbook_adapter import evaluate_orderbook_specialist


class MarketDataBrainTests(unittest.TestCase):
    def test_funding_uses_latest_settled_event_not_future_event(self):
        snapshot = MarketSnapshot("BTC", 100_000, "1h", {
            "funding_events": [
                {"timestamp_ms": 99_000, "funding_rate": 0.0002},
                {"timestamp_ms": 100_001, "funding_rate": -0.0005},
            ]
        })
        rows = evaluate_derivatives_specialists(snapshot)
        funding = next(row for row in rows if row.brain_id.endswith("funding"))
        self.assertEqual(funding.direction, "SHORT")
        self.assertIn("event_timestamp_ms:99000", funding.reasons)

    def test_stale_funding_event_is_unavailable(self):
        snapshot = MarketSnapshot("BTC", 10_000_000, "1h", {
            "funding_events": [{"timestamp_ms": 1, "funding_rate": 0.0005}]
        })
        funding = next(row for row in evaluate_derivatives_specialists(snapshot)
                       if row.brain_id.endswith("funding"))
        self.assertFalse(funding.available)
        self.assertEqual(funding.direction, "NO_TRADE")

    def test_missing_funding_is_unavailable_not_a_zero_signal(self):
        rows = evaluate_derivatives_specialists(MarketSnapshot("BTC", 100_000, "1h"))
        funding = next(row for row in rows if row.brain_id.endswith("funding"))
        self.assertFalse(funding.available)
        self.assertEqual(funding.direction, "NO_TRADE")

    def test_stale_open_interest_does_not_vote(self):
        snapshot = MarketSnapshot("BTC", 10_000_000, "1h", {
            "open_interest": {
                "timestamp_ms": 1, "change_pct": 5.0, "price_change_pct": 2.0,
            }
        })
        oi = next(row for row in evaluate_derivatives_specialists(snapshot)
                  if row.brain_id.endswith("open_interest"))
        self.assertFalse(oi.available)
        self.assertEqual(oi.direction, "NO_TRADE")

    def test_orderbook_requires_bid_ask_imbalance_and_microprice_confirmation(self):
        snapshot = MarketSnapshot("BTC", 100_000, "1m", {
            "orderbook": {
                "timestamp_ms": 99_900,
                "bids": [[100.0, 20.0], [99.9, 10.0]],
                "asks": [[100.1, 5.0], [100.2, 4.0]],
            }
        })
        result = evaluate_orderbook_specialist(snapshot)
        self.assertEqual(result.brain_id, "market.orderbook_imbalance")
        self.assertEqual(result.direction, "LONG")
        self.assertTrue(result.available)

    def test_stale_orderbook_does_not_vote(self):
        snapshot = MarketSnapshot("BTC", 100_000, "1m", {
            "orderbook": {
                "timestamp_ms": 1,
                "bids": [[100.0, 20.0]],
                "asks": [[100.1, 5.0]],
            }
        })
        result = evaluate_orderbook_specialist(snapshot)
        self.assertFalse(result.available)
        self.assertEqual(result.direction, "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
