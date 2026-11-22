import unittest

import pandas as pd

from mi_core.indicator_brain import evaluate_indicator_brain


class IndicatorBrainTests(unittest.TestCase):
    def test_rejects_non_dataframe(self):
        result = evaluate_indicator_brain([])
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "ohlcv_must_be_dataframe")

    def test_reports_missing_ohlcv_columns(self):
        frame = pd.DataFrame({"close": [100.0] * 100})
        result = evaluate_indicator_brain(frame)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "missing_ohlcv_columns")
        self.assertEqual(set(result["missing"]), {"open", "high", "low", "volume"})

    def test_requires_sufficient_completed_bars(self):
        frame = pd.DataFrame({
            "open": [100.0] * 20,
            "high": [101.0] * 20,
            "low": [99.0] * 20,
            "close": [100.0] * 20,
            "volume": [10.0] * 20,
        })
        result = evaluate_indicator_brain(frame)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "insufficient_ohlcv_history")


if __name__ == "__main__":
    unittest.main()
