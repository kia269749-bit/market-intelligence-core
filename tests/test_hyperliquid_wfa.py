import unittest

from mi_core.hyperliquid_data import (
    FundingEvent,
    PerpCandle,
    fetch_candles,
    fetch_funding_history,
    join_funding_feature,
    funding_cost_pct,
)
from mi_core.hyperliquid_wfa import trade_cost_components_pct
from mi_core.block_bootstrap import daily_block_bootstrap_mean_ci


class HyperliquidDataTests(unittest.TestCase):
    def test_fetch_candles_parses_and_sorts_public_api_rows(self):
        def fake(payload):
            self.assertEqual(payload["type"], "candleSnapshot")
            return [
                {"t": 3, "T": 4, "o": "102", "h": "104", "l": "101", "c": "103", "v": "12", "n": 7},
                {"t": 1, "T": 2, "o": "100", "h": "102", "l": "99", "c": "101", "v": "10", "n": 5},
            ]
        rows = fetch_candles("BTC", "1h", 0, 10, post_json=fake)
        self.assertEqual([row.timestamp_ms for row in rows], [1, 3])
        self.assertEqual(rows[0].close, 101.0)

    def test_funding_history_parses_realized_events(self):
        def fake(payload):
            self.assertEqual(payload["type"], "fundingHistory")
            return [
                {"coin": "BTC", "time": 2000, "fundingRate": "0.0001"},
                {"coin": "BTC", "time": 1000, "fundingRate": "-0.0002"},
            ]
        rows = fetch_funding_history("BTC", 0, 3000, post_json=fake)
        self.assertEqual([row.timestamp_ms for row in rows], [1000, 2000])
        self.assertAlmostEqual(rows[0].rate, -0.0002)

    def test_funding_history_chunks_long_ranges(self):
        calls = []
        def fake(payload):
            calls.append((payload["startTime"], payload["endTime"]))
            return [{
                "coin": "BTC", "time": payload["startTime"],
                "fundingRate": "0.0001",
            }]
        end = 30 * 24 * 60 * 60 * 1000
        rows = fetch_funding_history("BTC", 0, end, post_json=fake)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row.timestamp_ms for row in rows}), 3)

    def test_funding_feature_does_not_use_event_at_candle_close(self):
        candles = [
            PerpCandle("BTC", 0, 1000, 100, 102, 99, 101, 10, 1),
            PerpCandle("BTC", 1000, 2000, 101, 103, 100, 102, 10, 1),
            PerpCandle("BTC", 2000, 3000, 102, 104, 101, 103, 10, 1),
        ]
        events = [FundingEvent("BTC", 2000, 0.0003)]
        self.assertEqual(join_funding_feature(candles, events), [None, None, 0.0003])

    def test_funding_cost_uses_entry_notional_reference(self):
        result = funding_cost_pct(1, 2, [(110, 0.001), (120, 0.001)], entry_oracle_price=100)
        self.assertAlmostEqual(result, 0.23)

    def test_itemized_cost_has_side_aware_funding_and_separate_slippage(self):
        candles = [
            PerpCandle("BTC", 0, 1000, 100, 105, 99, 100, 10, 1),
            PerpCandle("BTC", 1000, 2000, 100, 111, 99, 110, 10, 1),
        ]
        funding = [FundingEvent("BTC", 1500, 0.001)]
        long = trade_cost_components_pct(
            entry_price=100, exit_price=110, side=1, funding_events=funding,
            candles=candles, entry_ts=1000, exit_ts=2000,
            slippage_bps_per_side=2,
        )
        short = trade_cost_components_pct(
            entry_price=100, exit_price=110, side=-1, funding_events=funding,
            candles=candles, entry_ts=1000, exit_ts=2000,
            slippage_bps_per_side=2,
        )
        self.assertAlmostEqual(long["fee_pct"], 0.0945)
        self.assertAlmostEqual(long["slippage_pct"], 0.042)
        self.assertAlmostEqual(long["funding_cost_pct"], 0.1)
        self.assertAlmostEqual(short["funding_cost_pct"], -0.1)
        self.assertGreater(long["total_itemized_cost_pct"], short["total_itemized_cost_pct"])

    def test_bootstrap_is_deterministic_and_keeps_day_clusters(self):
        day = 86_400_000
        observations = [
            (1 * day, 1.0), (1 * day + 1, -1.0),
            (2 * day, 3.0), (2 * day + 1, 3.0),
            (3 * day, -2.0),
        ]
        a = daily_block_bootstrap_mean_ci(observations, n_resamples=500, seed=7, block_days=1)
        b = daily_block_bootstrap_mean_ci(observations, n_resamples=500, seed=7, block_days=1)
        self.assertEqual(a, b)
        self.assertEqual(a["n_days"], 3)
        self.assertEqual(a["n_trades"], 5)
        self.assertEqual(a["status"], "OK")

    def test_bootstrap_uses_calendar_days_across_gaps(self):
        day = 86_400_000
        observations = [
            (1 * day, 1.0),
            (1 * day + 1, 3.0),
            (4 * day, -2.0),
            (8 * day, 4.0),
        ]
        for block_days in (1, 3, 7):
            with self.subTest(block_days=block_days):
                result = daily_block_bootstrap_mean_ci(
                    observations,
                    n_resamples=500,
                    seed=20261029,
                    block_days=block_days,
                )
                self.assertEqual(result["status"], "OK")
                self.assertEqual(result["n_days"], 3)
                self.assertEqual(result["n_calendar_days"], 8)
                self.assertEqual(result["block_days"], block_days)
                self.assertEqual(
                    result["effective_block_days"], min(block_days, 8)
                )
                self.assertEqual(result["resamples"], 500)

    def test_bootstrap_calendar_gap_changes_multiday_timeline(self):
        day = 86_400_000
        contiguous = [
            (1 * day, 1.0),
            (2 * day, -1.0),
            (3 * day, 2.0),
        ]
        with_gap = [
            (1 * day, 1.0),
            (4 * day, -1.0),
            (8 * day, 2.0),
        ]
        contiguous_result = daily_block_bootstrap_mean_ci(
            contiguous, n_resamples=500, seed=11, block_days=3
        )
        gap_result = daily_block_bootstrap_mean_ci(
            with_gap, n_resamples=500, seed=11, block_days=3
        )
        self.assertEqual(contiguous_result["n_calendar_days"], 3)
        self.assertEqual(gap_result["n_calendar_days"], 8)
        self.assertEqual(contiguous_result["effective_block_days"], 3)
        self.assertEqual(gap_result["effective_block_days"], 3)
        self.assertNotEqual(
            contiguous_result["ci_low_pct"], gap_result["ci_low_pct"]
        )

    def test_bootstrap_marks_single_day_insufficient(self):
        result = daily_block_bootstrap_mean_ci(
            [(1_000, 0.5), (2_000, -0.2)], n_resamples=500
        )
        self.assertEqual(result["status"], "INSUFFICIENT_DAYS")
        self.assertIsNone(result["ci_low_pct"])


if __name__ == "__main__":
    unittest.main()
