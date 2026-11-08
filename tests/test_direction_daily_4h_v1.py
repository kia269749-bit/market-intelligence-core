import importlib.util
import json
import unittest
import tempfile
from pathlib import Path

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "direction_daily_4h_v1.py"
SPEC = importlib.util.spec_from_file_location("direction_daily_4h_v1_tested", TOOL_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DirectionEvaluationTests(unittest.TestCase):
    def test_confusion_matrix_and_balanced_accuracy(self):
        result = MODULE.confusion([
            ("UP", "UP"),
            ("UP", "DOWN"),
            ("DOWN", "DOWN"),
            ("DOWN", "UP"),
        ])
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["balanced_accuracy"], 0.5)
        self.assertEqual(
            result["confusion_up_positive"],
            {"TP": 1, "TN": 1, "FP": 1, "FN": 1},
        )

    def test_score_reports_abstentions_and_coverage(self):
        samples = [
            {"decision_ts": 1, "label": "UP"},
            {"decision_ts": 2, "label": "DOWN"},
        ]
        result = MODULE.score(samples, {"1": "UP", "2": None})
        self.assertEqual(result["n"], 1)
        self.assertEqual(result["eligible_target_samples"], 2)
        self.assertEqual(result["no_prediction_count"], 1)
        self.assertEqual(result["coverage"], 0.5)

    def test_ema_resets_after_gap(self):
        rows = []
        for i in range(205):
            ts = i * MODULE.DAY_MS
            if i >= 205:
                ts += MODULE.DAY_MS
            rows.append({
                "ts": ts,
                "end": ts + MODULE.DAY_MS,
                "close": 100.0 + i,
            })
        rows.append({
            "ts": rows[-1]["ts"] + 3 * MODULE.DAY_MS,
            "end": rows[-1]["ts"] + 4 * MODULE.DAY_MS,
            "close": 999.0,
        })
        signal = MODULE.ema_at_each_bar(rows, MODULE.DAY_MS)
        self.assertIsNotNone(signal[rows[199]["end"]])
        self.assertIsNone(signal[rows[-1]["end"]])

    def test_sample_diagnostics_count_zero_return_and_alignment(self):
        day = MODULE.DAY_MS
        daily = [
            {"ts": 1577836800000 + i * day,
             "end": 1577836800000 + (i + 1) * day,
             "open": 100.0, "high": 102.0, "low": 99.0,
             "close": close}
            for i, close in enumerate([100.0, 101.0, 101.0, 99.0, 100.0])
        ]
        h4 = [
            {"ts": r["end"] - MODULE.H4_MS, "end": r["end"]}
            for r in daily
        ]
        h4_ends = {r["end"] for r in h4}
        dsig = {end: "UP" for end in h4_ends}
        hsig = {end: "UP" for end in h4_ends}
        diagnostics = {}
        samples = MODULE.make_samples(daily, h4, dsig, hsig, diagnostics)
        self.assertEqual(diagnostics["decision_candidates"], 4)
        self.assertEqual(diagnostics["exact_zero_returns_excluded"], 1)
        self.assertEqual(diagnostics["valid_nonzero_target_samples"], len(samples))


    def test_loader_uses_canonical_end_and_stops_before_cutoff_row(self):
        ts = 1735516800000  # 2024-12-30 00:00:00 UTC
        row = {
            "ts": ts,
            "interval": "1d",
            "close_time": ts + MODULE.DAY_MS - 2,
            "open": "100",
            "high": "105",
            "low": "99",
            "close": "104",
        }
        cutoff_row_is_intentionally_invalid_json = (
            '{"ts":1735689600000,"incomplete":\n'
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.jsonl"
            path.write_text(
                json.dumps(row) + "\n" + cutoff_row_is_intentionally_invalid_json,
                encoding="utf-8",
            )
            rows = MODULE.load_before_cutoff(path, "1d")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["end"], ts + MODULE.DAY_MS)
        self.assertEqual(rows[0]["reported_end"], ts + MODULE.DAY_MS - 1)
        self.assertTrue(rows[0]["close_time_anomaly"])

    def test_period_boundary(self):
        self.assertEqual(MODULE.period_of(1672531200000), "B")
        self.assertIsNone(MODULE.period_of(MODULE.CUTOFF))


if __name__ == "__main__":
    unittest.main()
