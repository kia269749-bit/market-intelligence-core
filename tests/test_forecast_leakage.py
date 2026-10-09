import unittest
from unittest.mock import patch

from mi_core.models import MarketBar
from mi_core.validated_forecast import (
    forecast_now,
    walk_forward_forecast,
    non_overlapping_predictions,
    score_predictions,
    score_capital_targets,
)
from mi_core.economic_edge import diagnose_economic_edge


class ForecastLeakageTests(unittest.TestCase):
    def _bars(self, n=180):
        return [MarketBar(ts=i, symbol="BTC", price=100.0 + i * 0.1) for i in range(n)]

    def test_live_forecast_training_uses_only_matured_labels(self):
        bars = self._bars(120)
        features = [[i] for i in range(len(bars))]
        labels = [1] * len(bars)
        seen = []

        def fit(x, y):
            seen.append(max(row[0] for row in x))
            return "model"

        with patch("mi_core.validated_forecast._feature_cache", return_value=features), \
             patch("mi_core.validated_forecast._labels_cache", return_value=labels), \
             patch("mi_core.validated_forecast._fit", side_effect=fit), \
             patch("mi_core.validated_forecast._predict", return_value={1: 0.8, 0: 0.1, -1: 0.1}):
            result = forecast_now(bars, horizon=5, train_window=100)

        self.assertTrue(result["available"])
        self.assertEqual(seen, [len(bars) - 1 - 5])

    def test_walk_forward_never_trains_on_unresolved_forward_labels(self):
        bars = self._bars(180)
        features = [[i] for i in range(len(bars))]
        labels = [1] * len(bars)
        seen = []

        def fit(x, y):
            seen.append(max(row[0] for row in x))
            return "model"

        with patch("mi_core.validated_forecast._feature_cache", return_value=features), \
             patch("mi_core.validated_forecast._labels_cache", return_value=labels), \
             patch("mi_core.validated_forecast._fit", side_effect=fit), \
             patch("mi_core.validated_forecast._predict", return_value={1: 0.8, 0: 0.1, -1: 0.1}):
            result = walk_forward_forecast(bars, horizon=5, train_window=100, min_train=60, fit_every=1)

        self.assertTrue(result["available"])
        self.assertTrue(seen)
        self.assertEqual(seen[0], 80)
        self.assertEqual(seen[-1], len(bars) - 2 * 5 - 1)
        self.assertEqual(seen, list(range(seen[0], seen[-1] + 1)))

    def test_economic_metrics_do_not_count_overlapping_forecasts_as_trades(self):
        result = {
            "horizon_bars": 3,
            "predictions": [{
                "ts": i, "actual": 1, "pred": 1,
                "actual_return_pct": 1.5, "favorable_mfe_pct": 1.7,
                "adverse_mae_pct": 0.2, "p_up": 0.8, "p_flat": 0.1, "p_down": 0.1,
            } for i in range(12)],
        }
        metrics = score_predictions(result)
        capital = score_capital_targets(result)
        edge = diagnose_economic_edge(result)
        self.assertEqual(metrics["resolved"], 4)
        self.assertEqual(metrics["all_forecasts"], 12)
        self.assertEqual(capital["resolved_directional"], 4)
        self.assertEqual(edge["samples"], 4)

    def test_non_overlapping_predictions_respect_horizon(self):
        result = {
            "horizon_bars": 3,
            "predictions": [{"ts": i, "actual": 1, "pred": 1} for i in range(12)],
        }
        rows = non_overlapping_predictions(result)
        self.assertEqual([row["ts"] for row in rows], [0, 3, 6, 9])


if __name__ == "__main__":
    unittest.main()
