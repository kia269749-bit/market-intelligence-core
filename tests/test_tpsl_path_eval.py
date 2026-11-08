import unittest
from mi_core.tpsl_path_eval import evaluate_signal, evaluate_signals


def make(rows):
    return [
        {"ts": i * 60000, "open": o, "high": h, "low": lo, "close": c}
        for i, (o, h, lo, c) in enumerate(rows)
    ]


class TPSLTests(unittest.TestCase):
    def test_long_tp_only(self):
        b = make([(100, 100.5, 99.5, 100), (100, 102, 99.8, 101)])
        r = evaluate_signal(b, 0, "LONG", 1, 0.5, 1, 0.1)
        self.assertEqual(r["status"], "TP")
        self.assertAlmostEqual(r["net_pct"], 0.9)

    def test_short_sl_only(self):
        b = make([(100, 100.2, 99.8, 100), (100, 100.8, 99.5, 100.2)])
        r = evaluate_signal(b, 0, "SHORT", 1, 0.5, 1)
        self.assertEqual(r["status"], "SL")
        self.assertAlmostEqual(r["gross_pct"], -0.5)

    def test_same_candle_both_levels_is_ambiguous(self):
        b = make([(100, 100.2, 99.8, 100), (100, 102, 99, 101)])
        r = evaluate_signal(b, 0, "LONG", 1, 0.5, 1)
        self.assertEqual(r["status"], "AMBIGUOUS")
        self.assertIsNone(r["net_pct"])

    def test_stop_first_is_explicit_sensitivity(self):
        b = make([(100, 100.2, 99.8, 100), (100, 102, 99, 101)])
        r = evaluate_signal(b, 0, "LONG", 1, 0.5, 1, ambiguous_policy="stop_first")
        self.assertEqual(r["status"], "SL_FIRST_ASSUMED")

    def test_gap_through_stop_after_entry(self):
        b = make([
            (100, 100.2, 99.8, 100),
            (100, 100.2, 99.8, 100),
            (98, 99, 97, 98.5),
        ])
        r = evaluate_signal(b, 0, "LONG", 1, 0.5, 2)
        self.assertEqual(r["status"], "SL_GAP")
        self.assertEqual(r["exit_price"], 98)
        self.assertAlmostEqual(r["gross_pct"], -2)

    def test_time_exit_cost_and_horizon(self):
        b = make([
            (100, 100.2, 99.8, 100),
            (100, 100.2, 99.8, 100.1),
            (100.1, 100.4, 100, 100.3),
        ])
        r = evaluate_signal(b, 0, "LONG", 5, 5, 2, 0.2)
        self.assertEqual(r["status"], "TIME_EXIT")
        self.assertAlmostEqual(r["net_pct"], 0.1)

    def test_incomplete_horizon_unavailable(self):
        b = make([(100, 100.2, 99.8, 100), (100, 100.2, 99.8, 100)])
        r = evaluate_signal(b, 0, "LONG", 5, 5, 2)
        self.assertEqual(r["status"], "UNAVAILABLE_HORIZON")

    def test_invalid_ohlc_rejected(self):
        b = make([(100, 99, 98, 100)])
        with self.assertRaises(ValueError):
            evaluate_signal(b, 0, "LONG", 1, 1, 1)

    def test_train_trade_cannot_cross_split(self):
        rows = []
        for i in range(20):
            p = 100 + i * 0.01
            rows.append((p, p + 0.1, p - 0.1, p))
        report = evaluate_signals(
            make(rows),
            [{"signal_index": 9, "side": "LONG"},
             {"signal_index": 12, "side": "LONG"}],
            5, 5, 3, train_fraction=0.6,
        )
        self.assertEqual(report["split_index"], 12)
        self.assertTrue(all(t["signal_index"] != 9 for t in report["trades"]))
        self.assertTrue(report["research_only"])
        self.assertFalse(report["live_orders"])


if __name__ == "__main__":
    unittest.main()
