import json
import tempfile
import unittest
from pathlib import Path

from mi_core.brains.contracts import BrainProposal, BrainResult, MarketSnapshot
from mi_core.brains.signal_journal import SignalJournal


class SignalJournalTests(unittest.TestCase):
    def test_repeated_directional_calls_are_cooldown_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = SignalJournal(Path(directory) / "signals.jsonl")
            proposal = BrainProposal("technical.strategy.ema_trend.1h", "technical", "LONG", 0.8, 100_000)
            decision = BrainResult("LONG", "BTCUSDT", 100_000, 0.8)
            first = journal.append(MarketSnapshot("BTCUSDT", 100_000, "1h", {"price": 100}), [proposal], decision)
            repeated = journal.append(MarketSnapshot("BTCUSDT", 130_000, "1h", {"price": 101}), [
                BrainProposal("technical.strategy.ema_trend.1h", "technical", "LONG", 0.8, 130_000)
            ], BrainResult("LONG", "BTCUSDT", 130_000, 0.8))
            self.assertEqual(len(first), 1)
            self.assertEqual(repeated, ())

    def test_journals_every_specialist_including_unavailable_no_trade(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = SignalJournal(Path(directory) / "signals.jsonl")
            snapshot = MarketSnapshot("BTC", 100_000, "1h")
            proposals = [
                BrainProposal("ta.1h", "technical", "LONG", 0.8, 100_000),
                BrainProposal("funding", "derivatives", "NO_TRADE", 0.0, 100_000, available=False),
            ]
            decision = BrainResult("NO_TRADE", "BTC", 100_000, 0.0)
            ids = journal.append(snapshot, proposals, decision)
            rows = [json.loads(line) for line in (Path(directory) / "signals.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(set(ids)), 2)
            self.assertEqual(rows[1]["direction"], "NO_TRADE")
            self.assertFalse(rows[1]["available"])
            self.assertEqual(rows[0]["central_decision"], "NO_TRADE")


if __name__ == "__main__":
    unittest.main()
