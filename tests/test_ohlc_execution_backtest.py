import unittest
from mi_core.models import MarketBar
from tools.ohlc_execution_backtest import _simulate, backtest


def bar(i, price, op=None, high=None, low=None):
    return MarketBar(ts=i * 300_000, symbol="BTCUSDT", price=price,
                     open=op if op is not None else price,
                     high=high if high is not None else price,
                     low=low if low is not None else price,
                     funding=0.00001,
                     derivatives={"funding_timestamp_ms": i * 300_000 - 1,
                                  "funding_age_ms": 1,
                                  "funding_max_age_ms": 7_200_000})


class OhlcExecutionTests(unittest.TestCase):
    def test_stop_wins_when_target_and_stop_touch_same_bar(self):
        bars = [bar(0, 100), bar(1, 100), bar(2, 100, high=102, low=99)]
        candidate = [{"index": 0, "ts": 0, "direction": "UP", "confidence": .8, "target_probability": .7}]
        trades = _simulate(bars, candidate, 1.0, .5, .12, horizon_bars=2)
        self.assertEqual(trades[0]["exit_reason"], "STOP")
        self.assertAlmostEqual(trades[0]["exit_price"], 99.5)
        self.assertAlmostEqual(trades[0]["net_return_pct"], -0.62)

    def test_simulator_applies_directional_funding_cashflow(self):
        bars = [bar(0, 100), bar(1, 100), bar(2, 100)]
        candidate = [{"index": 0, "ts": 0, "direction": "UP", "confidence": .8, "target_probability": .7}]
        trades = _simulate(
            bars, candidate, 5.0, 5.0, 0.15, horizon_bars=1,
            funding_events=[(300_000, 0.001)], funding_event_times=[300_000],
            funding_verified=True,
        )
        self.assertEqual(trades[0]["funding_events_count"], 1)
        self.assertAlmostEqual(trades[0]["funding_cost_pct"], 0.1)
        self.assertAlmostEqual(trades[0]["net_return_pct"], -0.22)

    def test_short_stop_gap_uses_worse_open(self):
        bars = [bar(0, 100), bar(1, 100), bar(2, 102, op=102, high=103, low=101)]
        candidate = [{"index": 0, "ts": 0, "direction": "DOWN", "confidence": .8, "target_probability": .7}]
        trades = _simulate(bars, candidate, 1.0, .5, .12, horizon_bars=2)
        self.assertEqual(trades[0]["exit_reason"], "STOP")
        self.assertEqual(trades[0]["exit_price"], 102.0)
        self.assertLess(trades[0]["gross_return_pct"], 0)

    def test_close_only_data_is_rejected(self):
        bars = [MarketBar(ts=i, symbol="BTCUSDT", price=100.0) for i in range(500)]
        result = backtest(bars, min_history=300, horizon_bars=96)
        self.assertEqual(result["status"], "ohlc_unavailable")
        self.assertFalse(result["trade_ready"])

    def test_backtest_refuses_economic_scoring_without_fresh_funding(self):
        bars = [
            MarketBar(ts=i * 300_000, symbol="BTCUSDT", price=100 + i * 0.01,
                      open=100 + i * 0.01, high=101 + i * 0.01, low=99 + i * 0.01)
            for i in range(500)
        ]
        result = backtest(bars, min_history=300, horizon_bars=24, step_bars=24, max_evals=4)
        self.assertFalse(result["funding_data_verified"])
        self.assertEqual(result["status"], "funding_unverified")
        self.assertTrue(all(x["full_walk_forward"]["trades"] == 0 for x in result["results"]))

    def test_backtest_uses_single_central_base_cost(self):
        bars = [bar(i, 100 + i * .01) for i in range(500)]
        result = backtest(bars, min_history=300, horizon_bars=24, step_bars=24, max_evals=4)
        self.assertAlmostEqual(result["cost_round_trip_pct"], 0.12)
        self.assertEqual([x["target_pct"] for x in result["results"][:2]], [0.92, 2.12])
        self.assertEqual(result["cost_mode"], "base")

    def test_metrics_report_research_only_and_no_trade_ready(self):
        bars = [bar(i, 100 + i * .01) for i in range(500)]
        result = backtest(bars, min_history=300, horizon_bars=24, step_bars=24, max_evals=4,
                          target_levels=(1.15,), stop_levels=(.5,))
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertFalse(result["trade_ready"])
        self.assertIn("holdout_oos", result["results"][0])


if __name__ == "__main__":
    unittest.main()
