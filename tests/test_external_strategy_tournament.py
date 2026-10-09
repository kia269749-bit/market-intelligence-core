import math
import unittest

from mi_core.models import MarketBar
from tools.external_strategy_tournament import STRATEGY_NAMES, build_signals, tournament


def make_bars(n=800):
    bars = []
    for i in range(n):
        # Deterministic trend plus cycles exercises both trend and reversal rules.
        close = 100.0 + 0.035 * i + 2.5 * math.sin(i / 9.0) + 0.8 * math.sin(i / 2.7)
        op = close * (1.0 + 0.0015 * math.sin(i / 3.0))
        high = max(op, close) * 1.004
        low = min(op, close) * 0.996
        bars.append(MarketBar(
            ts=i * 86_400_000, symbol="BTCUSDT", price=close,
            open=op, high=high, low=low, volume=1000.0,
        ))
    return bars


class ExternalStrategyTournamentTests(unittest.TestCase):
    def test_fixed_strategy_families_are_present_and_positions_bounded(self):
        bars = make_bars()
        signals = build_signals(bars)
        self.assertEqual(set(signals), set(STRATEGY_NAMES))
        for signal in signals.values():
            self.assertEqual(len(signal), len(bars))
            self.assertTrue(set(signal).issubset({-1.0, 0.0, 1.0}))

    def test_tournament_uses_chronological_holdout_and_never_marks_trade_ready(self):
        result = tournament(make_bars(), cost_round_trip_pct=0.35, capital_usd=500)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["bars"], 800)
        self.assertLess(result["common_evaluation_start_ts"], result["holdout_start_ts"])
        self.assertEqual(set(result["strategy_results"]), set(STRATEGY_NAMES))
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertFalse(result["trade_ready"])
        for item in result["strategy_results"].values():
            self.assertIn("development", item)
            self.assertIn("holdout_oos", item)
            self.assertIn("full_sample", item)
            self.assertGreater(item["holdout_oos"]["bars"], 0)

    def test_insufficient_data_is_not_accepted(self):
        result = tournament(make_bars(500))
        self.assertEqual(result["status"], "insufficient_data")
        self.assertFalse(result["trade_ready"])
        self.assertFalse(result["live_orders"])

    def test_duplicate_timestamps_are_rejected(self):
        bars = make_bars()
        bars[10] = MarketBar(ts=bars[9].ts, symbol=bars[10].symbol,
                             price=bars[10].price, open=bars[10].open,
                             high=bars[10].high, low=bars[10].low)
        with self.assertRaises(ValueError):
            tournament(bars)

    def test_invalid_ohlc_is_rejected(self):
        bars = make_bars()
        bad = bars[250]
        bars[250] = MarketBar(ts=bad.ts, symbol=bad.symbol, price=bad.price,
                              open=bad.open, high=bad.low, low=bad.high)
        with self.assertRaises(ValueError):
            tournament(bars)


if __name__ == "__main__":
    unittest.main()
