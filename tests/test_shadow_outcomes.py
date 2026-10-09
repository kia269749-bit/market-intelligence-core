import json
import tempfile
import unittest
from pathlib import Path

from mi_core.shadow_risk import build_risk_levels
from mi_core.paper_journal import append_signal, resolve_open_signals, summarize


class ShadowOutcomeTests(unittest.TestCase):
    def test_bullish_levels_are_two_to_one(self):
        r=build_risk_levels(100.0,"BULLISH",2.0)
        self.assertAlmostEqual(r["stop"],99.0)
        self.assertAlmostEqual(r["target"],102.0)
        self.assertEqual(r["risk_reward"],2.0)

    def test_bearish_levels_are_directional(self):
        r=build_risk_levels(100.0,"BEARISH",2.0)
        self.assertAlmostEqual(r["stop"],101.0)
        self.assertAlmostEqual(r["target"],98.0)

    def test_target_resolution_records_net_profit(self):
        with tempfile.TemporaryDirectory() as td:
            p=str(Path(td)/"shadow.jsonl")
            append_signal(p,{"signal_id":"x","direction":"BULLISH","entry_price":100.0,
                             "stop":99.0,"target":102.0,"capital_usd":500.0,
                             "round_trip_cost_pct":0.35,"research_only":True})
            self.assertEqual(resolve_open_signals(p,102.0,now=200),1)
            s=summarize(p)
            self.assertEqual(s["resolved"],1)
            self.assertEqual(s["wins"],1)
            self.assertAlmostEqual(s["net_profit_usd"],8.25,places=4)

    def test_target_overshoot_is_capped_at_target_price(self):
        with tempfile.TemporaryDirectory() as td:
            p=str(Path(td)/"shadow.jsonl")
            append_signal(p,{"signal_id":"x","direction":"BULLISH","entry_price":100.0,
                             "stop":99.0,"target":102.0,"capital_usd":500.0,
                             "round_trip_cost_pct":0.35,"research_only":True})
            self.assertEqual(resolve_open_signals(p,105.0,now=200),1)
            row=json.loads(Path(p).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["exit_price"],102.0)
            self.assertEqual(row["observed_price"],105.0)
            self.assertAlmostEqual(row["net_profit_usd"],8.25,places=4)

    def test_stop_gap_uses_worse_observed_price(self):
        with tempfile.TemporaryDirectory() as td:
            p=str(Path(td)/"shadow.jsonl")
            append_signal(p,{"signal_id":"x","direction":"BULLISH","entry_price":100.0,
                             "stop":99.0,"target":102.0,"capital_usd":500.0,
                             "round_trip_cost_pct":0.35,"research_only":True})
            self.assertEqual(resolve_open_signals(p,95.0,now=200),1)
            row=json.loads(Path(p).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["exit_price"],95.0)
            self.assertAlmostEqual(row["net_profit_usd"],-26.75,places=4)

    def test_stop_resolution_records_loss(self):
        with tempfile.TemporaryDirectory() as td:
            p=str(Path(td)/"shadow.jsonl")
            append_signal(p,{"signal_id":"x","direction":"BEARISH","entry_price":100.0,
                             "stop":101.0,"target":98.0,"capital_usd":500.0,
                             "round_trip_cost_pct":0.35,"research_only":True})
            self.assertEqual(resolve_open_signals(p,101.0,now=200),1)
            s=summarize(p)
            self.assertEqual(s["losses"],1)
            self.assertLess(s["net_profit_usd"],0)

    def test_asset_price_map_does_not_cross_resolve_assets(self):
        with tempfile.TemporaryDirectory() as td:
            p=str(Path(td)/"shadow.jsonl")
            append_signal(p,{"signal_id":"btc","asset":"BTC","direction":"BULLISH","entry_price":100.0,
                             "stop":99.0,"target":102.0,"capital_usd":500.0,
                             "round_trip_cost_pct":0.35,"research_only":True})
            append_signal(p,{"signal_id":"eth","asset":"ETH","direction":"BULLISH","entry_price":2000.0,
                             "stop":1980.0,"target":2040.0,"capital_usd":500.0,
                             "round_trip_cost_pct":0.35,"research_only":True})
            self.assertEqual(resolve_open_signals(p,{"BTC":102.0,"ETH":2000.0},now=200),1)
            rows=[json.loads(line) for line in Path(p).read_text(encoding="utf-8").splitlines()]
            states={r["asset"]:r["status"] for r in rows}
            self.assertEqual(states["BTC"],"TARGET")
            self.assertEqual(states["ETH"],"OPEN")

if __name__=="__main__":
    unittest.main()
