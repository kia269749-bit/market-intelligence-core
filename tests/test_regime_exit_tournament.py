import unittest

from mi_core.models import MarketBar
from tools.regime_exit_tournament import _trade, _evaluate, evaluate
from mi_core.adaptive_selector import STRATEGIES, _signal


class RegimeExitTournamentTests(unittest.TestCase):
    def _bars(self, n=420):
        rows = []
        for i in range(n):
            price = 100.0 + 0.08 * i
            rows.append(MarketBar(
                ts=i, symbol="BTCUSDT", price=price,
                open=price, high=price + 1.0, low=price - 1.0,
                volume=1000.0, buy_volume=120.0, sell_volume=80.0,
                oi=10000.0 + i, funding=0.0001,
            ))
        return rows

    def test_same_bar_stop_and_target_uses_conservative_stop(self):
        bars = self._bars(80)
        i = 30
        entry = bars[i + 1].price
        # Prior ATR is 2.0. Next bar touches both stop (entry-2) and target (entry+3).
        bars[i + 2] = MarketBar(
            ts=i + 2, symbol="BTCUSDT", price=entry,
            open=entry, high=entry + 4.0, low=entry - 3.0,
        )
        result = _trade(bars, i, 1, horizon=5, cost_pct=0.35,
                        stop_atr=1.0, target_atr=1.5)
        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "both_stop_first")
        self.assertAlmostEqual(result["net_pct"], -2.35, places=5)

    def test_train_trades_cannot_exit_across_split_boundary(self):
        bars = self._bars(420)
        signals = {name: [_signal(bars, i, name) for i in range(len(bars))]
                   for name in STRATEGIES}
        _, rows = _evaluate(bars, signals, "momentum_5", 10, 0.35,
                            1.0, 1.5, 60, 300)
        self.assertTrue(all(row["exit_index"] < 300 for row in rows))

    def test_evaluation_is_research_only_and_selection_is_training_only(self):
        result = evaluate(self._bars(), horizon=10, cost_pct=0.35,
                          holdout_bars=240)
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertLessEqual(len(result["selected_on_training_only"]), 3)
        self.assertEqual(len(result["training_metrics"]), 33)
        self.assertEqual(len(result["holdout_metrics_all_families_exploratory"]), 33)


if __name__ == "__main__":
    unittest.main()
