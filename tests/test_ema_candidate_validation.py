import math
import unittest
from types import SimpleNamespace

from tools.ema_candidate_validation import build_signals, validate_bars, validate_candidate


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

    def test_report_is_research_only_and_includes_cost_sensitivity(self):
        report = validate_candidate(make_bars(), expected_symbol="BTCUSDT", costs=(0.24, 0.36, 0.48))
        self.assertEqual(report["symbol"], "BTCUSDT")
        self.assertEqual(set(report["aggregate_by_cost"]), {"0.24", "0.36", "0.48"})
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])
        self.assertFalse(report["trade_ready"])
        self.assertIn("buy_and_hold", report["aggregate_by_cost"]["0.24"])

    def test_bad_ohlc_is_rejected(self):
        rows = make_bars()
        rows[100].high = rows[100].low / 2
        with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
            validate_bars(rows, expected_symbol="BTCUSDT")


if __name__ == "__main__":
    unittest.main()
