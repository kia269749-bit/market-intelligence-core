import math
import unittest
from types import SimpleNamespace

from tools.ema_candidate_validation import build_signals, validate_bars, validate_candidate, _moving_block_mean_ci, infer_interval_seconds, score_window


def make_bars(symbol="BTCUSDT", count=750):
    rows = []
    price = 100.0
    for i in range(count):
        # Deterministic trend plus bounded oscillation to exercise entries/exits.
        price *= 1.0015 if (i // 80) % 2 == 0 else 0.999
        close = price * (1.0 + 0.008 * math.sin(i / 7.0))
        open_price = close * (1.0 + 0.002 * math.sin(i / 3.0))
        high = max(open_price, close) * 1.004
        low = min(open_price, close) * 0.996
        rows.append(SimpleNamespace(
            ts=1609459200000 + i * 86400000,
            symbol=symbol,
            open=open_price,
            high=high,
            low=low,
            price=close,
        ))
    return rows


class EmaCandidateValidationTests(unittest.TestCase):
    def test_symbol_identity_is_enforced(self):
        rows = make_bars("ETHUSDT")
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            validate_bars(rows, expected_symbol="BTCUSDT")

    def test_duplicate_or_unsorted_timestamps_are_rejected(self):
        rows = make_bars()
        rows[20].ts = rows[19].ts
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            validate_bars(rows, expected_symbol="BTCUSDT")

    def test_future_bars_do_not_change_prior_signals(self):
        rows = make_bars(count=750)
        original = build_signals(rows)
        extended = build_signals(rows + make_bars(count=20)[-20:])
        for strategy in original:
            self.assertEqual(original[strategy][:700], extended[strategy][:700])

    def test_report_is_research_only_and_locks_project_cost(self):
        report = validate_candidate(make_bars(), expected_symbol="BTCUSDT", costs=(0.24,))
        self.assertEqual(report["symbol"], "BTCUSDT")
        self.assertEqual(set(report["aggregate_by_cost"]), {"0.24"})
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])
        self.assertFalse(report["trade_ready"])
        self.assertIn("buy_and_hold", report["aggregate_by_cost"]["0.24"])
        self.assertIn("ema20_50_sma200_confirmed", report["aggregate_by_cost"]["0.24"])
        self.assertIn("median_window_net_profit_usd", report["aggregate_by_cost"]["0.24"]["ema20_50"])
        with self.assertRaisesRegex(ValueError, "fixed at 0.24%"):
            validate_candidate(make_bars(), expected_symbol="BTCUSDT", costs=(0.36,))

    def test_block_bootstrap_is_reproducible_and_reports_uncertainty(self):
        values = [0.1] * 200
        first = _moving_block_mean_ci(values, block_length=20, replicates=200, seed=7)
        second = _moving_block_mean_ci(values, block_length=20, replicates=200, seed=7)
        self.assertEqual(first, second)
        self.assertGreater(first["ci95_low_mean_bar_excess_pct"], 0.0)

    def test_interval_aware_sharpe_uses_bar_frequency(self):
        rows = make_bars(count=750)
        for i, row in enumerate(rows):
            row.ts = 1609459200000 + i * 4 * 3600000
        self.assertEqual(infer_interval_seconds(rows), 14400.0)
        result = score_window(rows, [1.0] * len(rows), 200, 300, 0.24)
        self.assertEqual(result["bar_interval_seconds"], 14400.0)
        self.assertIn("annualized_sharpe_approx", result)
        self.assertIn("mean_bar_net_pct", result)
        self.assertNotIn("daily_sharpe_approx", result)

    def test_long_short_ema_candidates_can_take_short_positions(self):
        rows = []
        price = 200.0
        for i in range(400):
            price *= 0.998
            rows.append(SimpleNamespace(
                ts=1609459200000 + i * 4 * 3600000,
                symbol="BTCUSDT",
                open=price * 1.001,
                high=price * 1.003,
                low=price * 0.997,
                price=price,
            ))
        signals = build_signals(rows)
        self.assertTrue(any(x < 0 for x in signals["ema20_50_long_short"]))
        self.assertTrue(any(x < 0 for x in signals["ema20_50_sma200_long_short"]))
        self.assertTrue(all(x in (-1.0, 0.0, 1.0) for x in signals["ema20_50_sma200_long_short"]))

    def test_bad_ohlc_is_rejected(self):
        rows = make_bars()
        rows[100].high = rows[100].low / 2
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            validate_bars(rows, expected_symbol="BTCUSDT")


if __name__ == "__main__":
    unittest.main()
