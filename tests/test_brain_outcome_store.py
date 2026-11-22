import json
import tempfile
import unittest
from pathlib import Path

from mi_core.brains.outcome_store import OutcomeStore


class BrainOutcomeStoreTests(unittest.TestCase):
    def test_append_only_outcome_counts_resolved_wins_and_losses(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OutcomeStore(Path(directory) / "outcomes.jsonl")
            base = {"signal_id": "s1", "brain_id": "technical.rsi", "family": "technical", "symbol": "BTC", "direction": "LONG", "resolved": True, "won": True}
            store.append(base)
            store.append({**base, "signal_id": "s2", "won": False})
            self.assertEqual(store.performance("technical.rsi"), {"wins": 1, "losses": 1})
            self.assertEqual(len((Path(directory) / "outcomes.jsonl").read_text().splitlines()), 2)

    def test_fixed_horizon_resolution_applies_cost_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            signal_path = root / "signals.jsonl"
            signal_path.write_text(json.dumps({
                "signal_id": "sig-1", "brain_id": "technical.strategy.ema_trend.1h",
                "family": "technical", "symbol": "BTCUSDT", "timeframe": "1h",
                "direction": "LONG", "available": True, "entry_price": 100.0,
                "as_of_ms": 1_000_000, "regime": "TREND",
            }) + "\n")
            store = OutcomeStore(root / "outcomes.jsonl")
            self.assertEqual(store.resolve_due_signals(
                signal_path, {"BTCUSDT": 101.0}, 1_000_000 + 3_600_000 + 1_000,
                round_trip_cost_pct=0.12,
            ), 1)
            self.assertEqual(store.performance("technical.strategy.ema_trend.1h"), {"wins": 1, "losses": 0})
            self.assertEqual(store.resolve_due_signals(
                signal_path, {"BTCUSDT": 102.0}, 1_000_000 + 7_200_000,
                round_trip_cost_pct=0.12,
            ), 0)

    def test_unresolved_is_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OutcomeStore(Path(directory) / "outcomes.jsonl")
            row = {"signal_id": "s1", "brain_id": "flow", "family": "orderflow", "symbol": "BTC", "direction": "SHORT", "resolved": False, "won": None}
            store.append(row)
            self.assertEqual(store.performance("flow"), {"wins": 0, "losses": 0})


if __name__ == "__main__":
    unittest.main()
