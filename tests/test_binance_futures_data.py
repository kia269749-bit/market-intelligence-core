import json
import tempfile
import unittest
from pathlib import Path

from mi_core.binance_futures_data import (
    FUNDING_URL,
    KLINES_URL,
    OPEN_INTEREST_URL,
    FundingEvent,
    FuturesCandle,
    OpenInterestSnapshot,
    download_project60,
    fetch_futures_klines,
    fetch_funding_rate_history,
    fetch_open_interest_history,
    project60_rows,
)


class BinanceFuturesDataTests(unittest.TestCase):
    def _kline(self, open_ms=0, close_ms=59_999):
        return [
            open_ms, "100", "102", "99", "101", "10", close_ms,
            "1010", "5", "4", "404", "0",
        ]

    def test_futures_klines_parse_usdm_ohlcv_and_taker_buy_quote(self):
        def fake(url, params, timeout=20):
            self.assertEqual(url, KLINES_URL)
            self.assertEqual(params["symbol"], "BTCUSDT")
            return [self._kline()]
        candles = fetch_futures_klines("btcusdt", "1m", limit=1, start_ms=0, end_ms=60_000, get_json=fake)
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].close, 101.0)
        self.assertEqual(candles[0].taker_buy_quote_volume, 404.0)

    def test_futures_klines_paginate_beyond_exchange_page_limit(self):
        calls = []
        def fake(url, params, timeout=20):
            calls.append(dict(params))
            if len(calls) == 1:
                return [self._kline(i * 60_000, (i + 1) * 60_000 - 1) for i in range(1000)]
            return [self._kline(60_000_000, 60_059_999)]
        candles = fetch_futures_klines(
            "BTCUSDT", "1m", limit=1001, start_ms=0, end_ms=60_060_000, get_json=fake
        )
        self.assertEqual(len(candles), 1001)
        self.assertEqual([x["limit"] for x in calls], [1000, 1])
        self.assertEqual(calls[1]["startTime"], 60_000_000)

    def test_open_interest_history_paginates_without_repeating_cursor(self):
        calls = []
        def fake(url, params, timeout=20):
            self.assertEqual(url, OPEN_INTEREST_URL)
            calls.append(params["startTime"])
            if len(calls) == 1:
                return [{"timestamp": 100, "sumOpenInterest": "10", "sumOpenInterestValue": "1000"}]
            if len(calls) == 2:
                return [{"timestamp": 200, "sumOpenInterest": "11", "sumOpenInterestValue": "1100"}]
            return []
        rows = fetch_open_interest_history(
            "BTCUSDT", "1h", 0, 300, get_json=fake, page_limit=1
        )
        self.assertEqual([x.timestamp_ms for x in rows], [100, 200])
        self.assertEqual(calls, [0, 101, 201])

    def test_funding_history_parses_and_sorts_events(self):
        def fake(url, params, timeout=20):
            self.assertEqual(url, FUNDING_URL)
            return [
                {"fundingTime": 40_000, "fundingRate": "0.0001"},
                {"fundingTime": 20_000, "fundingRate": "-0.0002"},
            ]
        rows = fetch_funding_rate_history("BTCUSDT", 0, 60_000, get_json=fake)
        self.assertEqual([x.timestamp_ms for x in rows], [20_000, 40_000])
        self.assertAlmostEqual(rows[0].rate, -0.0002)

    def test_asof_join_excludes_event_at_exact_candle_close(self):
        candles = [
            FuturesCandle("BTCUSDT", 0, 60_000, 100, 102, 99, 101, 10, 1000, 400, 5),
            FuturesCandle("BTCUSDT", 60_000, 120_000, 101, 103, 100, 102, 11, 1100, 450, 6),
        ]
        oi = [
            OpenInterestSnapshot("BTCUSDT", 60_000, 10, 1000),
            OpenInterestSnapshot("BTCUSDT", 90_000, 11, 1100),
        ]
        funding = [FundingEvent("BTCUSDT", 60_000, 0.0001)]
        rows, coverage = project60_rows(candles, oi, funding)
        first = rows[0]["coins"]["BTCUSDT"]
        second = rows[1]["coins"]["BTCUSDT"]
        self.assertIsNone(first["open_interest"])
        self.assertIsNone(first["funding"])
        self.assertEqual(second["open_interest"], 11.0)
        self.assertAlmostEqual(second["funding"], 0.0001)
        self.assertEqual(coverage["alignment"], "strictly_before_candle_close_no_lookahead")

    def test_download_refuses_to_overwrite_existing_file_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "existing.jsonl"
            target.write_text("keep-me\\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                download_project60("BTCUSDT", "1m", 1, str(target), get_json=lambda *a, **k: [])
            self.assertEqual(target.read_text(encoding="utf-8"), "keep-me\\n")

    def test_download_writes_project60_rows_and_coverage(self):
        def fake(url, params, timeout=20):
            if url == KLINES_URL:
                return [self._kline()]
            if url == OPEN_INTEREST_URL:
                return [{"timestamp": 30_000, "sumOpenInterest": "10", "sumOpenInterestValue": "1000"}]
            if url == FUNDING_URL:
                return [{"fundingTime": 40_000, "fundingRate": "0.0001"}]
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as td:
            path, coverage = download_project60(
                "BTCUSDT", "1m", 1, str(Path(td) / "futures.jsonl"),
                start_ms=0, end_ms=60_000, get_json=fake
            )
            row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        asset = row["coins"]["BTCUSDT"]
        self.assertEqual(asset["open_interest"], 10.0)
        self.assertAlmostEqual(asset["funding"], 0.0001)
        self.assertEqual(coverage["oi_coverage_pct"], 100.0)
        self.assertEqual(coverage["funding_coverage_pct"], 100.0)
        self.assertEqual(coverage["oi_period"], "5m")
        self.assertEqual(coverage["oi_history_max_days"], 30)
        self.assertFalse(coverage["features_enabled"])


if __name__ == "__main__":
    unittest.main()
