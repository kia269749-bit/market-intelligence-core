import json
import tempfile
import unittest
from pathlib import Path

from mi_core.hyperliquid_data import (
    CHUNK_MS,
    download_project60,
    fetch_candles,
    fetch_funding_history,
    join_funding_feature,
    project60_rows,
    PerpCandle,
    FundingEvent,
)


class HyperliquidProject60Tests(unittest.TestCase):
    def _candle(self, ts=0, close_ts=3_599_999):
        return {
            "t": ts, "T": close_ts, "o": "100", "h": "102",
            "l": "99", "c": "101", "v": "12", "n": 7,
        }

    def test_candle_history_is_chunked_and_sorted(self):
        calls = []
        def fake(payload):
            calls.append(payload)
            start = payload["req"]["startTime"]
            return [self._candle(start, start + 3_599_999)]
        rows = fetch_candles("BTC", "1h", 0, 30 * 24 * 60 * 60 * 1000, post_json=fake)
        self.assertEqual(len(calls), 3)
        self.assertEqual([x.timestamp_ms for x in rows], [0, CHUNK_MS, 2 * CHUNK_MS])

    def test_funding_history_chunks_and_sorts_events(self):
        calls = []
        def fake(payload):
            calls.append(payload)
            return [{"coin": "BTC", "time": payload["startTime"], "fundingRate": "0.0001"}]
        end = 30 * 24 * 60 * 60 * 1000
        rows = fetch_funding_history("BTC", 0, end, post_json=fake)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(rows), 3)
        self.assertEqual([x.timestamp_ms for x in rows], sorted(x.timestamp_ms for x in rows))

    def test_project60_funding_join_is_strictly_backward(self):
        candles = [
            PerpCandle("BTC", 0, 60_000, 100, 102, 99, 101, 10, 5),
            PerpCandle("BTC", 60_000, 120_000, 101, 103, 100, 102, 11, 6),
        ]
        events = [FundingEvent("BTC", 60_000, 0.0001)]
        rows, coverage = project60_rows("BTC", "BTCUSDT", candles, events)
        first = rows[0]["coins"]["BTCUSDT"]
        second = rows[1]["coins"]["BTCUSDT"]
        self.assertIsNone(first["funding"])
        self.assertAlmostEqual(second["funding"], 0.0001)
        self.assertIsNone(first["open_interest"])
        self.assertEqual(coverage["oi_status"], "no_historical_oi_feed_in_this_adapter")
        self.assertEqual(coverage["alignment"], "funding_events_strictly_before_candle_close_no_lookahead")

    def test_funding_feature_carries_last_known_rate_without_lookahead(self):
        candles = [
            PerpCandle("BTC", 0, 1000, 100, 102, 99, 101, 10, 5),
            PerpCandle("BTC", 1000, 2000, 101, 103, 100, 102, 11, 6),
            PerpCandle("BTC", 2000, 3000, 102, 104, 101, 103, 12, 7),
        ]
        events = [FundingEvent("BTC", 2000, 0.0003)]
        self.assertEqual(join_funding_feature(candles, events), [None, None, 0.0003])

    def test_download_writes_project60_and_refuses_overwrite(self):
        def fake(payload):
            if payload["type"] == "candleSnapshot":
                return [self._candle(0, 3_599_999)]
            if payload["type"] == "fundingHistory":
                return [{"coin": "BTC", "time": 1_800_000, "fundingRate": "0.0001"}]
            raise AssertionError(payload)
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "hyperliquid.jsonl"
            path, coverage = download_project60(
                "BTC", "1h", 1, str(target), asset_key="BTCUSDT",
                start_ms=0, end_ms=3_600_000, post_json=fake,
            )
            row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            asset = row["coins"]["BTCUSDT"]
            self.assertEqual(asset["open"], 100.0)
            self.assertAlmostEqual(asset["funding"], 0.0001)
            self.assertEqual(coverage["funding_coverage_pct"], 100.0)
            self.assertEqual(coverage["oi_coverage_pct"], 0.0)
            with self.assertRaises(FileExistsError):
                download_project60("BTC", "1h", 1, str(target), post_json=fake)


if __name__ == "__main__":
    unittest.main()
