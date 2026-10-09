import unittest
from types import SimpleNamespace
from mi_core.models import MarketBar
from tools.economic_path_validation import validate, _path_stats, _future_index


class TestEconomicPathValidation(unittest.TestCase):
    def test_actual_clock_validation_is_research_only(self):
        bars=[]
        price=100.0
        for i in range(180):
            price*=1.001 if i%4 else 0.999
            bars.append(MarketBar(ts=i*3600,symbol="BTCUSDT",price=price,
                                  buy_volume=120,sell_volume=80,volume=100))
        r=validate(bars,minutes=(60,),costs=(0.10,0.35),min_history=120,step=12,max_evals=3)
        self.assertEqual(r["status"],"ok")
        self.assertEqual(r["minutes"],[60])
        self.assertEqual(r["costs"],[0.10,0.35])
        self.assertTrue(r["research_only"])
        self.assertFalse(r["live_orders"])
        self.assertIn("cost_sensitivity",r)
        self.assertIn("horizon_results",r)
        self.assertFalse(r["portfolio_simulated"])
        self.assertFalse(r["trade_ready"])
        self.assertIn("by_horizon", r["cost_sensitivity"]["0.35"])
        self.assertIn("fixed_horizon_close_expectancy_pct", r["horizon_results"]["60"])
        self.assertIn("max_drawdown_pct_points", r["horizon_results"]["60"])

    def test_future_index_respects_millisecond_wall_clock_horizon(self):
        bars = [
            SimpleNamespace(ts=1_800_000_000_000 + i * 3_600_000)
            for i in range(4)
        ]
        # A 15-minute horizon on hourly data must resolve at the next hourly bar,
        # not compare milliseconds to seconds and silently act like a 1-bar horizon.
        self.assertEqual(_future_index(bars, 0, 15 * 60), 1)
        self.assertEqual(_future_index(bars, 0, 2 * 60 * 60), 2)

    def test_future_index_supports_second_timestamps(self):
        bars = [SimpleNamespace(ts=10_000 + i * 3_600) for i in range(4)]
        self.assertEqual(_future_index(bars, 0, 15 * 60), 1)
        self.assertEqual(_future_index(bars, 0, 2 * 60 * 60), 2)

    def test_short_adverse_excursion_tracks_upward_move(self):
        bars = [
            MarketBar(ts=i * 3600, symbol="BTCUSDT", price=p,
                      buy_volume=1, sell_volume=1, volume=2)
            for i, p in enumerate((100.0, 98.0, 101.0, 97.0))
        ]
        realized, mfe, mae = _path_stats(bars, 0, 3, "DOWN")
        self.assertAlmostEqual(realized, 3.0)
        self.assertAlmostEqual(mfe, 3.0)
        self.assertAlmostEqual(mae, 1.0)


if __name__=="__main__":
    unittest.main()
