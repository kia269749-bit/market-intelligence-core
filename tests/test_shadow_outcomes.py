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

    def test_duplicate_signal_id_rejected_after_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            p=str(Path(td)/"shadow.jsonl")
            signal={"signal_id":"unique-1","asset":"BTC",
                    "direction":"BULLISH","entry_price":100.0,
                    "stop":99.0,"target":102.0,"capital_usd":500.0,
                    "round_trip_cost_pct":0.35,"research_only":True}
            self.assertTrue(append_signal(p,signal))
            self.assertEqual(resolve_open_signals(p,102.0,now=200),1)
            self.assertFalse(append_signal(p,signal))
            self.assertEqual(len(Path(p).read_text().splitlines()),1)

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


    def test_stale_price_timestamp_does_not_resolve_signal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "journal.jsonl"
            append_signal(p, {
                "signal_id": "stale-ts",
                "asset": "BTC",
                "direction": "BULLISH",
                "entry_price": 100,
                "stop": 99,
                "target": 102,
                "forecast_ts": 100,
            })
            changed = resolve_open_signals(
                str(p), {"BTC": 102}, now=200, price_timestamp=100
            )
            self.assertEqual(changed, 0)
            row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["status"], "OPEN")

    def test_non_finite_price_does_not_resolve_signal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "journal.jsonl"
            append_signal(p, {
                "signal_id": "infinite-price",
                "asset": "BTC",
                "direction": "BULLISH",
                "entry_price": 100,
                "stop": 99,
                "target": 102,
            })
            changed = resolve_open_signals(
                str(p), {"BTC": float("inf")}, now=200
            )
            self.assertEqual(changed, 0)
            row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["status"], "OPEN")


    def test_old_market_observation_does_not_resolve_signal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "journal.jsonl"
            append_signal(p, {
                "signal_id": "old-observation",
                "asset": "BTC",
                "direction": "BULLISH",
                "entry_price": 100,
                "stop": 99,
                "target": 102,
                "forecast_ts": 100,
            })
            changed = resolve_open_signals(
                str(p), {"BTC": 102}, now=1000, price_timestamp=700
            )
            self.assertEqual(changed, 0)
            row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["status"], "OPEN")

if __name__=="__main__":
    unittest.main()
