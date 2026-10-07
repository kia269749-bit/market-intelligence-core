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
                "forecast": {"available": True, "asset": "BTC", "direction": "UP", "selected": {"current_price": 100.0, "asset": "BTC"}},
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

    def test_duplicate_open_signal_is_not_appended(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            self.assertTrue(_append_shadow_if_actionable(path,self._snapshot()))
            self.assertFalse(_append_shadow_if_actionable(path,self._snapshot()))
            rows=Path(path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows),1)

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

    def test_outcome_summary_groups_context(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            rows=[
                {
                    "status":"TARGET","direction":"BULLISH","regime":"TREND",
                    "confidence":0.82,"modeled_profit_usd":12.0,
                    "net_profit_usd":12.0,
                },
                {
                    "status":"STOP","direction":"BULLISH","regime":"TREND",
                    "confidence":0.68,"modeled_profit_usd":6.0,
                    "net_profit_usd":-4.0,
                },
                {
                    "status":"TARGET","direction":"BEARISH","regime":"RANGE",
                    "confidence":0.91,"modeled_profit_usd":5.0,
                    "net_profit_usd":5.0,
                },
            ]
            Path(path).write_text(
                "".join(json.dumps(r)+"\n" for r in rows),
                encoding="utf-8"
            )

            summary=summarize(path)

            self.assertEqual(summary["resolved"],3)
            self.assertEqual(summary["by_regime"]["TREND"]["resolved"],2)
            self.assertEqual(summary["by_regime"]["TREND"]["win_rate"],0.5)
            self.assertEqual(summary["by_direction"]["BULLISH"]["resolved"],2)
            self.assertEqual(summary["by_direction"]["BEARISH"]["wins"],1)
            self.assertEqual(summary["by_confidence"]["HIGH"]["resolved"],1)
            self.assertEqual(summary["by_confidence"]["MEDIUM"]["resolved"],1)
            self.assertEqual(summary["by_confidence"]["VERY_HIGH"]["resolved"],1)
            self.assertEqual(summary["by_economic_tier"]["PREFERRED"]["resolved"],1)
            self.assertEqual(summary["by_economic_tier"]["ACCEPTABLE"]["resolved"],2)

    def test_outcome_summary_empty_file_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"missing.jsonl")
            summary=summarize(path)
            self.assertEqual(summary["resolved"],0)
            self.assertEqual(summary["by_regime"],{})
            self.assertEqual(summary["by_direction"],{})
            self.assertEqual(summary["by_confidence"],{})
            self.assertEqual(summary["by_economic_tier"],{})


if __name__=="__main__":
    unittest.main()
