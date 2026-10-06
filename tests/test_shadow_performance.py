import json, tempfile, unittest
from pathlib import Path
from mi_core.shadow_performance import summarize_performance, format_performance_line

class ShadowPerformanceTests(unittest.TestCase):
    def _write(self,td,rows):
        p=Path(td)/"shadow.jsonl"; p.write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf-8"); return str(p)
    def test_performance_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            s=summarize_performance(self._write(td,[{"status":"TARGET","net_profit_usd":12.0},{"status":"TARGET","net_profit_usd":6.0},{"status":"STOP","net_profit_usd":-4.0},{"status":"STOP","net_profit_usd":-2.0},{"status":"OPEN","net_profit_usd":999.0}]))
            self.assertEqual(s["resolved"],4); self.assertEqual(s["wins"],2); self.assertEqual(s["losses"],2)
            self.assertEqual(s["win_rate"],0.5); self.assertEqual(s["net_profit_usd"],12.0)
            self.assertEqual(s["expectancy_usd"],3.0); self.assertEqual(s["profit_ge_4_usd"],2); self.assertEqual(s["profit_ge_10_usd"],1)
            self.assertEqual(s["max_drawdown_usd"],6.0); self.assertEqual(s["profit_factor"],3.0)
    def test_compact_live_line(self):
        line=format_performance_line({
            "resolved":4,"win_rate":0.5,"net_profit_usd":12.0,
            "expectancy_usd":3.0,"max_drawdown_usd":6.0,
            "profit_ge_4_usd":2,"profit_ge_10_usd":1,
        })
        self.assertEqual(line, "Shadow: 4 resolved | Win 50% | Net $+12.00 | Expectancy $+3.00 | DD $6.00 | ≥$4: 2 | ≥$10: 1")

    def test_empty_journal_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            s=summarize_performance(str(Path(td)/"missing.jsonl"))
            self.assertEqual(s["resolved"],0); self.assertEqual(s["net_profit_usd"],0.0)
            self.assertEqual(s["hit_rate_ge_10_usd"],0.0); self.assertTrue(s["research_only"]); self.assertFalse(s["live_orders"])
if __name__=="__main__": unittest.main()
