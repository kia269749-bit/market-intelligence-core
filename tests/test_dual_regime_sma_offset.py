import math
import unittest
from types import SimpleNamespace

from tools.dual_regime_sma_offset import (
    UNIVERSE, align_universe, build_candidate_signals, build_regime,
    simulate, random_matched_signals,
)


def bars(symbol, prices, start=1609459200000):
    out = []
    for i, close in enumerate(prices):
        op = close * (1.0 + (0.001 if i % 2 else -0.001))
        out.append(SimpleNamespace(
            ts=start + i * 4 * 60 * 60 * 1000,
            symbol=symbol, open=op, high=max(op, close) * 1.01,
            low=min(op, close) * 0.99, price=close,
        ))
    return out


class DualRegimeTests(unittest.TestCase):
    def test_alignment_fails_closed_when_any_universe_member_missing(self):
        data = {s: bars(s, [100.0] * 5) for s in UNIVERSE}
        data[UNIVERSE[-1]] = data[UNIVERSE[-1]][:-1]
        stamps, indexed = align_universe(data)
        self.assertEqual(len(stamps), 4)
        self.assertTrue(all(all(t in indexed[s] for s in UNIVERSE) for t in stamps))

    def test_future_bars_do_not_change_earlier_candidate_signals(self):
        prices = [100 + i * 0.2 + 2 * math.sin(i / 5) for i in range(500)]
        rows = bars("BTCUSDT", prices)
        regime = {r.ts: True for r in rows}
        first = build_candidate_signals(rows, regime, 0.05)["entry"]
        altered = rows[:]
        for r in altered[400:]:
            r.price *= 0.5
            r.low *= 0.5
            r.open *= 0.5
            r.high *= 0.5
        second = build_candidate_signals(altered, regime, 0.05)["entry"]
        self.assertEqual(first[:400], second[:400])

    def test_random_baseline_is_reproducible(self):
        rows = bars("BTCUSDT", [100 + i * 0.1 for i in range(100)])
        self.assertEqual(random_matched_signals(rows, 10, 17), random_matched_signals(rows, 10, 17))

    def test_cost_rate_is_locked_to_preregistered_scenarios(self):
        rows = bars("BTCUSDT", [100 + i * 0.1 for i in range(80)])
        with self.assertRaisesRegex(ValueError, "preregistered"):
            simulate(rows, [False] * len(rows), cost_pct=0.35)

    def test_circuit_breaker_triggers_after_20_percent_marked_drawdown(self):
        prices = [100.0] * 40 + [75.0] * 20
        rows = bars("BTCUSDT", prices)
        signals = [True] * len(rows)
        result = simulate(
            rows, signals, cost_pct=0.24, initial_equity=500,
            use_risk=False, use_stops=False, use_trailing=False,
            use_time_exit=False, circuit_breaker=True,
        )
        self.assertTrue(result["circuit_breaker_triggered"])

    def test_risk_sizing_caps_stop_risk_to_one_percent_before_slippage(self):
        prices = [100 + i * 0.05 + 1.5 * math.sin(i / 4) for i in range(100)]
        rows = bars("BTCUSDT", prices)
        entries = [False] * len(rows)
        entries[30] = True
        regime = [True] * len(rows)
        from tools.dual_regime_sma_offset import atr
        result = simulate(rows, {"entry": entries, "regime": regime, "atr": atr(rows)},
                          cost_pct=0.24, initial_equity=500, use_risk=True)
        if result["trades"]:
            trade = result["trades"][0]
            idx = next(i for i, r in enumerate(rows) if r.ts == trade["entry_ts"])
            atr_at_signal = atr(rows)[idx - 1]
            risk_per_unit = 2 * atr_at_signal + trade["entry"] * (0.24 / 100.0)
            self.assertLessEqual(trade["qty"] * risk_per_unit, 5.000001)


if __name__ == "__main__":
    unittest.main()
