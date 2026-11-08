import unittest
from mi_core.kronos_adapter import KronosConfig, validate_ohlcv_bars, validate_bar_interval, summarize_scenarios
from mi_core.models import MarketBar


class KronosAdapterTests(unittest.TestCase):
    def _bars(self, n=40):
        return [
            MarketBar(
                ts=1_700_000_000 + i * 3600,
                symbol="BTC",
                price=100.0 + i,
                volume=10.0,
                open=99.5 + i,
                high=101.0 + i,
                low=99.0 + i,
            )
            for i in range(n)
        ]

    def test_config_rejects_more_than_one_hundred_scenarios(self):
        with self.assertRaises(ValueError):
            KronosConfig(repo_path="/tmp/Kronos", scenario_count=101)

    def test_config_supports_mini_context_and_bounded_batches(self):
        config = KronosConfig(repo_path="/tmp/Kronos")
        self.assertEqual(config.max_context, 2048)
        self.assertEqual(config.batch_size, 4)

    def test_close_only_bars_are_rejected(self):
        rows = self._bars()
        rows[10] = MarketBar(ts=rows[10].ts, symbol="BTC", price=110.0)
        with self.assertRaisesRegex(ValueError, "missing_ohlc"):
            validate_ohlcv_bars(rows)

    def test_non_monotonic_timestamps_are_rejected(self):
        rows = self._bars()
        rows[12] = MarketBar(ts=rows[11].ts, symbol="BTC", price=112.0,
                             open=111.5, high=113.0, low=111.0)
        with self.assertRaisesRegex(ValueError, "timestamps_not_strictly_increasing"):
            validate_ohlcv_bars(rows)

    def test_irregular_bar_intervals_are_rejected(self):
        rows = self._bars()
        with self.assertRaisesRegex(ValueError, "irregular_bar_interval"):
            validate_bar_interval(rows, 60)

    def test_expected_bar_interval_is_accepted(self):
        rows = self._bars()
        validate_bar_interval(rows, 60)

    def test_inconsistent_ohlc_is_rejected(self):
        rows = self._bars()
        rows[4] = MarketBar(ts=rows[4].ts, symbol="BTC", price=104.0,
                            open=104.5, high=103.0, low=102.0)
        with self.assertRaisesRegex(ValueError, "inconsistent_ohlc"):
            validate_ohlcv_bars(rows)

    def test_scenario_summary_uses_median_and_quantile_bounds(self):
        paths = [
            [{"close": 100.0, "reference_close": 100.0}],
            [{"close": 110.0, "reference_close": 100.0}],
            [{"close": 120.0, "reference_close": 100.0}],
        ]
        result = summarize_scenarios(paths)
        self.assertEqual(result["scenario_count"], 3)
        self.assertEqual(result["summary"][0]["close_median"], 110.0)
        self.assertEqual(result["summary"][0]["close_p10"], 102.0)
        self.assertEqual(result["summary"][0]["close_p90"], 118.0)

