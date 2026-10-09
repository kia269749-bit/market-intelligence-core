import unittest
from mi_core.models import MarketBar
from tools.strategy_archetype_backtest import backtest, simulate, generate_signals


def bar(i, close=100.0, op=None, high=None, low=None):
    return MarketBar(
        ts=i * 3_600_000, symbol="BTCUSDT", price=close,
        open=close if op is None else op,
        high=close if high is None else high,
        low=close if low is None else low,
    )


class StrategyArchetypeBacktestTests(unittest.TestCase):
    def test_entry_uses_next_bar_open_and_charges_cost(self):
        rows = [bar(i) for i in range(65)]
        rows[61] = bar(61, close=100.8, op=100.3, high=101.0, low=100.0)
        trades = simulate(rows, {60: 1}, target_pct=1.15, stop_pct=.5,
                          cost_pct=.35, max_hold=1, cooldown=0)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_price"], 100.3)
        self.assertAlmostEqual(trades[0]["net_return_pct"], ((100.8/100.3)-1)*100-.35, places=5)

    def test_stop_first_if_both_levels_touch(self):
        rows = [bar(i) for i in range(65)]
        rows[61] = bar(61, close=100.0, op=100.0, high=102.0, low=99.0)
        trades = simulate(rows, {60: 1}, target_pct=1.0, stop_pct=.5,
                          cost_pct=.35, max_hold=1, cooldown=0)
        self.assertEqual(trades[0]["exit_reason"], "STOP")
        self.assertEqual(trades[0]["exit_price"], 99.5)
        self.assertAlmostEqual(trades[0]["net_return_pct"], -.85)

    def test_stress_cost_reduces_net_return(self):
        rows = [bar(i) for i in range(65)]
        rows[61] = bar(61, close=101.5, op=100.0, high=102.0, low=99.9)
        base = simulate(rows, {60: 1}, target_pct=1.0, stop_pct=.5,
                        cost_pct=.35, max_hold=1, cooldown=0)
        stress = simulate(rows, {60: 1}, target_pct=1.0, stop_pct=.5,
                          cost_pct=.50, max_hold=1, cooldown=0)
        self.assertEqual(base[0]["exit_reason"], "TARGET")
        self.assertAlmostEqual(base[0]["net_return_pct"] - stress[0]["net_return_pct"], .15)

    def test_archetypes_are_causal_and_report_is_research_only(self):
        rows = []
        price = 100.0
        for i in range(420):
            price *= 1.0005 if (i // 45) % 2 == 0 else .9995
            rows.append(bar(i, close=price, op=price, high=price*1.002, low=price*.998))
        signals = generate_signals(rows)
        self.assertTrue(set(signals).issuperset({"ema_trend_flip", "momentum_threshold_cross", "breakout_20"}))
        self.assertTrue(all(60 <= i < len(rows)-1 for mapping in signals.values() for i in mapping))
        result = backtest(rows)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertFalse(result["trade_ready"])
        self.assertIn("holdout_oos", result["results"][0])


if __name__ == "__main__":
    unittest.main()
