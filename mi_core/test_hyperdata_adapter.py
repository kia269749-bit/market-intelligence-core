"""Tests for the read-only HyperData order-flow adapter."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.hyperdata_adapter import evaluate_hyperdata_orderflow
from mi_core.brains.registry import list_specialist_sources


AS_OF_MS = 1_800_000_000_000
AS_OF = datetime.fromtimestamp(AS_OF_MS / 1000, timezone.utc).isoformat()


def _payload(**overrides):
    frame = {
        "net_usd": 250_000.0,
        "imbalance": 0.50,
        "signal": "STRONG_BULL",
        "window_coverage": 0.99,
    }
    frames = {tf: dict(frame) for tf in ("1m", "5m", "15m", "1h", "4h", "24h")}
    data = {
        "meta": {"as_of": AS_OF, "warnings": []},
        "venues": {"hyperliquid": "ok", "binance": "partial"},
        "timeframes": frames,
    }
    data.update(overrides)
    return data


def _snapshot(payload, age_ms=10_000):
    return MarketSnapshot(
        symbol="BTCUSDT",
        as_of_ms=AS_OF_MS + age_ms,
        timeframe="1h",
        payload={"hyperdata_orderflow": payload},
    )


class HyperDataAdapterTests(unittest.TestCase):
    def test_hyperdata_is_registered_as_one_dynamic_orderflow_source(self):
        sources = list_specialist_sources()
        item = sources["market.hyperdata_orderflow.dynamic"]
        self.assertEqual(item["family"], "orderflow")
        self.assertEqual(item["adapter"], "hyperdata_adapter")
        self.assertEqual(item["status"], "runnable_when_external_payload_present")

    def test_missing_external_payload_adds_no_proposals(self):
        snapshot = MarketSnapshot("BTCUSDT", AS_OF_MS, "1h", {})
        self.assertEqual(evaluate_hyperdata_orderflow(snapshot), [])

    def test_fresh_full_coverage_payload_produces_orderflow_family_proposals(self):
        proposals = evaluate_hyperdata_orderflow(_snapshot(_payload()))
        self.assertEqual(len(proposals), 6)
        one_minute = next(p for p in proposals if p.brain_id.endswith(".1m"))
        self.assertEqual(one_minute.direction, "LONG")
        self.assertEqual(one_minute.family, "orderflow")
        self.assertTrue(one_minute.available)
        self.assertLessEqual(one_minute.confidence, 0.95)
        self.assertIn("hyperliquid", one_minute.source_ids)

    def test_warming_up_window_is_not_a_vote(self):
        data = _payload()
        data["timeframes"]["5m"]["window_coverage"] = 0.50
        proposals = evaluate_hyperdata_orderflow(_snapshot(data))
        five_minute = next(p for p in proposals if p.brain_id.endswith(".5m"))
        self.assertFalse(five_minute.available)
        self.assertIn("warming_up", five_minute.reasons[0])

    def test_stale_feed_is_not_a_vote(self):
        proposals = evaluate_hyperdata_orderflow(_snapshot(_payload(), age_ms=90_000))
        self.assertTrue(all(not p.available for p in proposals))
        self.assertIn("stale", proposals[0].reasons[0])

    def test_no_contributing_venue_is_not_a_vote(self):
        data = _payload(venues={"hyperliquid": "silent", "binance": "frozen"})
        proposals = evaluate_hyperdata_orderflow(_snapshot(data))
        self.assertTrue(all(not p.available for p in proposals))

    def test_delta_and_imbalance_conflict_is_rejected(self):
        data = _payload()
        data["timeframes"]["1h"]["net_usd"] = -10_000
        proposals = evaluate_hyperdata_orderflow(_snapshot(data))
        one_hour = next(p for p in proposals if p.brain_id.endswith(".1h"))
        self.assertFalse(one_hour.available)
        self.assertIn("conflict", one_hour.reasons[0])

    def test_partial_only_venues_reduce_confidence(self):
        full = evaluate_hyperdata_orderflow(_snapshot(_payload()))
        partial_data = _payload(venues={"hyperliquid": "partial"})
        partial = evaluate_hyperdata_orderflow(_snapshot(partial_data))
        full_p = next(p for p in full if p.brain_id.endswith(".1m"))
        partial_p = next(p for p in partial if p.brain_id.endswith(".1m"))
        self.assertLess(partial_p.confidence, full_p.confidence)


if __name__ == "__main__":
    unittest.main()
