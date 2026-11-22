import unittest

from mi_core.brains.contracts import BrainProposal, MarketSnapshot
from mi_core.brains.orchestrator import arbitrate
from mi_core.brains.strategy_runtime import StrategyRegistration, StrategyRuntime


class BrainRuntimeTests(unittest.TestCase):
    def test_strategy_runtime_keeps_each_registered_brain_separate(self):
        runtime = StrategyRuntime()
        runtime.register(StrategyRegistration(
            "strategy.alpha", "strategy", "example/alpha",
            lambda snapshot: BrainProposal(
                "strategy.alpha", "strategy", "LONG", 0.8,
                snapshot.as_of_ms, ("example/alpha",), ("test",),
            ),
        ))
        runtime.register(StrategyRegistration(
            "strategy.beta", "strategy", "example/beta",
            lambda snapshot: BrainProposal(
                "strategy.beta", "strategy", "SHORT", 0.7,
                snapshot.as_of_ms, ("example/beta",), ("test",),
            ),
        ))
        results = runtime.evaluate(MarketSnapshot("BTC", 100_000, "1h"))
        self.assertEqual([row.brain_id for row in results], ["strategy.alpha", "strategy.beta"])
        self.assertEqual({row.direction for row in results}, {"LONG", "SHORT"})

    def test_strategy_runtime_turns_adapter_failure_into_unavailable_no_trade(self):
        runtime = StrategyRuntime()
        def broken(_snapshot):
            raise RuntimeError("offline")
        runtime.register(StrategyRegistration("strategy.broken", "strategy", "example/broken", broken))
        result = runtime.evaluate(MarketSnapshot("BTC", 100_000, "1h"))[0]
        self.assertEqual(result.direction, "NO_TRADE")
        self.assertFalse(result.available)

    def test_complete_payoff_estimate_must_clear_round_trip_cost(self):
        snapshot = MarketSnapshot("BTC", 100_000, "1h")
        good = BrainProposal(
            "a", "technical", "LONG", 0.9, 100_000,
            expected_win_rate=0.7, expected_win_pct=0.5, expected_loss_pct=0.5,
        )
        other = BrainProposal("b", "orderflow", "LONG", 0.8, 100_000)
        self.assertEqual(arbitrate(snapshot, [good, other]).decision, "LONG")

        bad = BrainProposal(
            "a", "technical", "LONG", 0.9, 100_000,
            expected_win_rate=0.5, expected_win_pct=0.1, expected_loss_pct=0.1,
        )
        self.assertEqual(arbitrate(snapshot, [bad, other]).decision, "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
