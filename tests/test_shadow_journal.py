import json
import tempfile
import unittest
from pathlib import Path

from mi_core.cli import _append_shadow_if_actionable
from mi_core.paper_journal import summarize, resolve_open_signals, apply_funding_settlements, settle_hyperliquid_funding


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
            self.assertAlmostEqual(row["stop"],98.75)
            self.assertAlmostEqual(row["target"],102.5)
            self.assertEqual(row["capital_usd"],500.0)
            self.assertEqual(row["round_trip_cost_pct"],0.15)
            self.assertEqual(row["funding_status"],"UNVERIFIED")
            self.assertFalse(row["learning_eligible"])
            self.assertTrue(row["research_only"])
            self.assertFalse(row["live_orders"])
            self.assertEqual(summarize(path)["count"],1)

    def test_forecast_top_level_price_is_used_when_selected_price_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            snapshot=self._snapshot()
            forecast=snapshot["evidence"]["forecast"]
            forecast["price"]=101.0
            forecast["selected"].pop("current_price")
            self.assertTrue(_append_shadow_if_actionable(path,snapshot))
            row=json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["entry_price"],101.0)
            self.assertAlmostEqual(row["target"],103.525)

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

    def test_shadow_resolution_uses_central_base_cost_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            Path(path).write_text(json.dumps({
                "status":"OPEN","asset":"BTC","direction":"BULLISH",
                "entry_price":100.0,"stop":99.0,"target":102.5,
                "capital_usd":500.0
            })+"\n",encoding="utf-8")
            self.assertEqual(resolve_open_signals(path,103.0,now=456),1)
            row=json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["round_trip_cost_pct"],0.15)
            self.assertAlmostEqual(row["net_profit_usd"],11.75)

    def test_funding_settlement_updates_net_pnl_and_learning_eligibility(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            row={
                "signal_id":"BTC:BULLISH:100.0","status":"TARGET",
                "capital_usd":500.0,"gross_move_pct":2.5,
                "round_trip_cost_pct":0.15,"net_profit_usd":11.75,
                "funding_status":"UNVERIFIED","funding_coverage":0.0,
                "learning_eligible":False,
            }
            Path(path).write_text(json.dumps(row)+"\n",encoding="utf-8")
            self.assertEqual(apply_funding_settlements(path,{
                "BTC:BULLISH:100.0":{"coverage":0.99,"events":3,"cashflow_usd":-0.75}
            }),1)
            updated=json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(updated["funding_status"],"VERIFIED")
            self.assertTrue(updated["learning_eligible"])
            self.assertAlmostEqual(updated["net_profit_usd"],11.0)
            self.assertEqual(summarize(path)["funding_verified_resolved"],1)

    def test_hyperliquid_funding_history_is_applied_to_resolved_shadow(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            row={
                "signal_id":"BTC:BULLISH:100.0","asset":"BTC","direction":"BULLISH",
                "status":"TARGET","ts":3600,"resolved_ts":7200,
                "capital_usd":500.0,"gross_move_pct":2.5,
                "round_trip_cost_pct":0.15,"net_profit_usd":11.75,
                "funding_status":"UNVERIFIED","funding_coverage":0.0,
                "learning_eligible":False,
            }
            Path(path).write_text(json.dumps(row)+"\n",encoding="utf-8")
            calls=[]
            def fake_fetch(coin,start_ms,end_ms):
                calls.append((coin,start_ms,end_ms))
                return [{"time":7200000,"fundingRate":"0.001"}]
            self.assertEqual(settle_hyperliquid_funding(path,fetcher=fake_fetch),1)
            updated=json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(calls,[("BTC",3600000,7200000)])
            self.assertEqual(updated["funding_events"],1)
            self.assertAlmostEqual(updated["funding_cashflow_usd"],-0.5)
            self.assertAlmostEqual(updated["net_profit_usd"],11.25)
            self.assertTrue(updated["learning_eligible"])

    def test_incomplete_funding_sample_is_excluded_from_outcome_memory(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            rows=[
                {"status":"TARGET","net_profit_usd":50.0,"funding_status":"UNVERIFIED"},
                {"status":"STOP","net_profit_usd":-20.0,"funding_status":"VERIFIED",
                 "funding_coverage":0.80,"funding_cashflow_usd":-1.0,"learning_eligible":True},
            ]
            Path(path).write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf-8")
            summary=summarize(path)
            self.assertEqual(summary["resolved_total"],2)
            self.assertEqual(summary["resolved"],0)
            self.assertEqual(summary["funding_incomplete_resolved"],2)
            self.assertEqual(summary["net_profit_usd"],0.0)

    def test_outcome_summary_groups_context(self):
        with tempfile.TemporaryDirectory() as td:
            path=str(Path(td)/"shadow.jsonl")
            rows=[
                {
                    "status":"TARGET","direction":"BULLISH","regime":"TREND",
                    "confidence":0.82,"modeled_profit_usd":12.0,
                    "net_profit_usd":12.0,"funding_status":"VERIFIED","funding_coverage":1.0,"funding_cashflow_usd":0.25,"learning_eligible":True,
                },
                {
                    "status":"STOP","direction":"BULLISH","regime":"TREND",
                    "confidence":0.68,"modeled_profit_usd":6.0,
                    "net_profit_usd":-4.0,"funding_status":"VERIFIED","funding_coverage":0.98,"funding_cashflow_usd":-0.1,"learning_eligible":True,
                },
                {
                    "status":"TARGET","direction":"BEARISH","regime":"RANGE",
                    "confidence":0.91,"modeled_profit_usd":5.0,
                    "net_profit_usd":5.0,"funding_status":"VERIFIED","funding_coverage":0.99,"funding_cashflow_usd":0.05,"learning_eligible":True,
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
