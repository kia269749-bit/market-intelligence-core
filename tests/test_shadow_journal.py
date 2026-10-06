import json
import tempfile
import unittest
from pathlib import Path

from mi_core.cli import _append_shadow_if_actionable
from mi_core.paper_journal import summarize


class ShadowJournalTests(unittest.TestCase):
    def _snapshot(self, actionable=True, approved=True, bias="BULLISH"):
        return {
            "ts": 123,
            "market": {"rows": [{"price": 100.0}]},
            "capital_economics": {
                "approved": approved,
                "expected_move_pct": 2.5,
                "required_move_pct": 1.15,
                "preferred_required_move_pct": 2.35,
                "modeled_profit_usd": 10.75,
            },
            "evidence": {
                "combined": {
                    "actionable": actionable,
                    "bias": bias,
                    "confidence": 0.80,
                    "agreement": 0.90,
                    "regime": "TREND",
                },
                "data_quality": {"status": "HEALTHY"},
                "forecast": {"available": True, "direction": "UP"},
            },
        }

    def test_actionable_approved_signal_is_appended(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            self.assertTrue(_append_shadow_if_actionable(path,self._snapshot()))
            rows=Path(path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows),1)
            row=json.loads(rows[0])
            self.assertEqual(row["status"],"OPEN")
            self.assertEqual(row["direction"],"BULLISH")
            self.assertEqual(row["entry_price"],100.0)
            self.assertTrue(row["research_only"])
            self.assertFalse(row["live_orders"])
            self.assertEqual(summarize(path)["count"],1)

    def test_blocked_or_unapproved_signal_is_not_appended(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            self.assertFalse(_append_shadow_if_actionable(path,self._snapshot(actionable=False)))
            self.assertFalse(_append_shadow_if_actionable(path,self._snapshot(approved=False)))
            self.assertFalse(Path(path).exists())

    def test_neutral_signal_is_not_appended(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            self.assertFalse(_append_shadow_if_actionable(path,self._snapshot(bias="NEUTRAL")))
            self.assertFalse(Path(path).exists())


if __name__=="__main__":
    unittest.main()
