import unittest
from unittest.mock import patch

from mi_core.models import MarketBar
from mi_core.path_forecast import HORIZONS
from tools.oos_multihorizon import evaluate


def make_segment(start, count, price=100.0):
    return [
        MarketBar(
            ts=start + i * 60,
            symbol="BTC",
            price=price + i * 0.1,
        )
        for i in range(count)
    ]


class OOSMultihorizonAlignmentTests(unittest.TestCase):
    def fake_economics(self, path, *, capital_usd, round_trip_cost_pct):
        return {
            "horizons": [
                {
                    "horizon": h,
                    "direction": "UP",
                    "expected_return_pct": 1.0,
                    "target_hit_probability": 0.5,
                    "tier": "VIABLE",
                }
                for h in HORIZONS
            ]
        }

    def test_duplicate_timestamps_are_removed_before_evaluation(self):
        bars = make_segment(0, 60)
        duplicate = MarketBar(
            ts=bars[10].ts,
            symbol="BTC",
            price=999.0,
        )
        bars.insert(12, duplicate)

        with patch(
            "tools.oos_multihorizon.forecast_path", return_value=object()
        ), patch(
            "tools.oos_multihorizon.path_to_economic_opportunity",
            side_effect=self.fake_economics,
        ):
            result = evaluate(
                bars, capital=500, cost_pct=0.35, step=10,
                min_history=2, max_eval=0, max_gap_seconds=300,
            )

        self.assertEqual(result["alignment"]["duplicates_removed"], 1)
        self.assertEqual(result["alignment"]["raw_count"], 61)

    def test_forecasts_never_cross_large_time_gaps(self):
        first = make_segment(0, 60)
        second = make_segment(20_000, 60)
        bars = first + second
        observed_histories = []

        def capture_history(history, *, min_history):
            observed_histories.append([bar.ts for bar in history])
            return object()

        with patch(
            "tools.oos_multihorizon.forecast_path",
            side_effect=capture_history,
        ), patch(
            "tools.oos_multihorizon.path_to_economic_opportunity",
            side_effect=self.fake_economics,
        ):
            result = evaluate(
                bars, capital=500, cost_pct=0.35, step=10,
                min_history=2, max_eval=0, max_gap_seconds=300,
            )

        self.assertEqual(result["alignment"]["segments_created"], 2)
        self.assertEqual(result["segments_evaluated"], 2)
        self.assertTrue(observed_histories)
        for history in observed_histories:
            self.assertTrue(
                all(b - a <= 300 for a, b in zip(history, history[1:])),
                msg=f"History crossed a temporal gap: {history}",
            )

    def test_short_segments_are_not_joined_to_reach_minimum_history(self):
        bars = make_segment(0, 30) + make_segment(10_000, 30)

        with patch(
            "tools.oos_multihorizon.forecast_path", return_value=object()
        ), patch(
            "tools.oos_multihorizon.path_to_economic_opportunity",
            side_effect=self.fake_economics,
        ):
            result = evaluate(
                bars, capital=500, cost_pct=0.35, step=1,
                min_history=10, max_eval=0, max_gap_seconds=300,
            )

        self.assertEqual(result["alignment"]["segments_created"], 2)
        self.assertEqual(result["segments_evaluated"], 0)
        for h in HORIZONS:
            self.assertEqual(result[str(h)]["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
