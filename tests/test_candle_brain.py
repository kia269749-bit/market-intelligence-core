import json
import tempfile
import unittest
from pathlib import Path

from mi_core.candle_brain import analyze_project60, build_candles
from mi_core.live_brain import _candle_adjustment


def _write_history(path):
    rows=[]
    price=100.0
    for i in range(80):
        if i == 74:
            price *= 0.985
        elif i == 75:
            price *= 0.998
        elif i == 76:
            price *= 1.012
        elif i == 77:
            price *= 1.004
        else:
            price *= 1.001
        buy=7000.0 if i>=76 else 2500.0
        sell=2000.0 if i>=76 else 2600.0
        rows.append({"timestamp":i*60000,"coins":{"BTC":{"price":price,"trades":{"buy_usd":buy,"sell_usd":sell}}}})
    path.write_text("\n".join(json.dumps(x) for x in rows),encoding="utf-8")


class CandleBrainTests(unittest.TestCase):
    def test_builds_candles_with_buy_sell_microstructure(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"market.jsonl"
            _write_history(p)
            candles=build_candles(p,"BTC",max_rows=80,span=5)
        self.assertGreaterEqual(len(candles),16)
        self.assertIn("delta_pct",candles[-1])
        self.assertIn("buy_volume_usd",candles[-1])
        self.assertIn("sell_volume_usd",candles[-1])

    def test_brain_is_advisory_and_reports_pattern_context(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"market.jsonl"
            _write_history(p)
            result=analyze_project60(p,"BTC",max_rows=80,candle_span=5,lookback=16)
        self.assertTrue(result["available"])
        self.assertTrue(result["research_only"])
        self.assertFalse(result["live_orders"])
        self.assertEqual(result["role"],"confidence_enhancer_only")
        self.assertIn("anatomy",result)
        self.assertIn("pattern_evidence",result)

    def test_alignment_only_gently_boosts_signal(self):
        aligned=_candle_adjustment({"available":True,"bias":"BULLISH","confidence":0.9},"BULLISH")
        contrary=_candle_adjustment({"available":True,"bias":"BEARISH","confidence":0.9},"BULLISH")
        self.assertGreater(aligned["factor"],1.0)
        self.assertLess(contrary["factor"],1.0)
        self.assertGreaterEqual(contrary["factor"],0.92)

if __name__=="__main__":
    unittest.main()
