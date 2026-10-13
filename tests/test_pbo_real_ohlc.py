import unittest

from tools.pbo_real_ohlc import build_aligned_return_matrix


class RealOHLCPCOTests(unittest.TestCase):
    def test_aligns_development_returns_and_purges_boundary_crossing_trade(self):
        timestamps = list(range(16))
        rows = [{
            "target_pct": 1.15,
            "stop_pct": 0.5,
            "cohort": "all_directional",
            "trades": [
                {"signal_ts": 1, "exit_ts": 3, "net_return_pct": 1.0},
                {"signal_ts": 8, "exit_ts": 13, "net_return_pct": 5.0},
                {"signal_ts": 12, "exit_ts": 14, "net_return_pct": -2.0},
            ],
        }]
        result = build_aligned_return_matrix(
            timestamps, rows, holdout_start_ts=12,
            n_blocks=4, min_development_trades=1,
        )
        name = "target=1.15|stop=0.5|cohort=all_directional"
        self.assertEqual(len(result["returns_by_strategy"][name]), 12)
        self.assertAlmostEqual(result["returns_by_strategy"][name][3], 0.01)
        self.assertEqual(sum(result["returns_by_strategy"][name]), 0.01)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["development_trades_used"], 1)
        self.assertEqual(candidate["purged_boundary_trades"], 1)
        self.assertEqual(candidate["holdout_trades"], 1)
        self.assertTrue(candidate["eligible_for_pbo"])

    def test_trims_incomplete_cscv_tail_consistently(self):
        timestamps = list(range(16))
        rows = [{
            "target_pct": 1.15,
            "stop_pct": 0.5,
            "cohort": "all_directional",
            "trades": [
                {"signal_ts": 10, "exit_ts": 12, "net_return_pct": 1.0},
            ],
        }]
        result = build_aligned_return_matrix(
            timestamps, rows, holdout_start_ts=13,
            n_blocks=4, min_development_trades=1,
        )
        self.assertEqual(result["development_bars_before_block_trim"], 13)
        self.assertEqual(result["development_bars_used_for_pbo"], 12)
        self.assertEqual(result["development_bars_trimmed_for_equal_blocks"], 1)
        self.assertEqual(result["candidates"][0]["excluded_incomplete_tail_trades"], 1)
        self.assertEqual(result["candidates"][0]["development_trades_used"], 0)

    def test_rejects_invalid_block_count(self):
        with self.assertRaises(ValueError):
            build_aligned_return_matrix(
                list(range(16)), [], holdout_start_ts=12, n_blocks=5
            )


if __name__ == "__main__":
    unittest.main()
