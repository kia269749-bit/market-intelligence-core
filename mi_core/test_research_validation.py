"""Tests for optional purgedcv research validation adapter."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from mi_core.research_validation import run_purgedcv_walk_forward


class _FakeWalkForward:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def split(self, values):
        yield list(range(0, 10)), list(range(10, 15))
        yield list(range(0, 15)), list(range(15, 20))


class PurgedCVAdapterTests(unittest.TestCase):
    def setUp(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.prediction_times = [base + timedelta(hours=i) for i in range(20)]
        self.evaluation_times = [value + timedelta(hours=1) for value in self.prediction_times]
        self.returns = [0.001 if i % 3 else -0.0005 for i in range(20)]

    def test_requires_net_of_cost_returns(self):
        with self.assertRaisesRegex(ValueError, "after all modeled costs"):
            run_purgedcv_walk_forward(
                self.returns, self.prediction_times, self.evaluation_times,
                returns_are_net=False,
            )

    def test_rejects_mismatched_timestamp_lengths(self):
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            run_purgedcv_walk_forward(
                self.returns, self.prediction_times[:-1], self.evaluation_times,
                returns_are_net=True,
            )

    def test_missing_optional_package_is_reported_not_installed(self):
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name == "purgedcv":
                raise ImportError("not installed in this environment")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            result = run_purgedcv_walk_forward(
                self.returns, self.prediction_times, self.evaluation_times,
                returns_are_net=True,
            )
        self.assertFalse(result["available"])
        self.assertEqual(result["required_extra"], "cloud-validation")

    def test_walk_forward_wrapper_passes_temporal_boundaries_and_reports_oos(self):
        fake = types.ModuleType("purgedcv")
        fake.WalkForwardSplit = _FakeWalkForward
        fake.probabilistic_sharpe_ratio = lambda values, benchmark_skill: 0.75
        fake.deflated_sharpe_ratio_full = lambda values, n_trials, var_sharpe: SimpleNamespace(
            dsr=0.62, sr_star=0.03
        )
        with patch.dict(sys.modules, {"purgedcv": fake}):
            result = run_purgedcv_walk_forward(
                self.returns, self.prediction_times, self.evaluation_times,
                returns_are_net=True, n_splits=2, test_size=5,
                purge_horizon="1h", embargo="30min", n_trials=10, var_sharpe=0.01,
            )
        self.assertTrue(result["available"])
        self.assertEqual(result["oos_samples"], 10)
        self.assertEqual(result["dsr"], 0.62)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])


if __name__ == "__main__":
    unittest.main()
