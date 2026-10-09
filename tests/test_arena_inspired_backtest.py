import unittest
from unittest.mock import patch
import tools.arena_inspired_backtest as arena
from tools.arena_inspired_backtest import backtest

class ArenaInspiredTests(unittest.TestCase):
    def test_research_only_and_costs(self):
        rows=[]
        p=100.0
        for i in range(120):
            p*=1.001
            rows.append({"ts":i,"o":p,"h":p*1.002,"l":p*.998,"c":p,"v":100.0})
        r=backtest(rows)
        self.assertTrue(r["research_only"])
        self.assertFalse(r["live_orders"])
        self.assertAlmostEqual(r["cost_model_round_trip_pct"],0.35)
    def test_entry_uses_next_bar_open(self):
        rows=[]
        p=100.0
        for i in range(180):
            p*=1.001
            rows.append({"ts":i,"o":p*1.0002,"h":p*1.002,"l":p*.998,"c":p,"v":100.0})
        with patch.object(arena, "ema", side_effect=lambda xs, n: [100.0 if n == 20 else 99.0 for _ in xs]), \
             patch.object(arena, "atr", return_value=[0.1]*len(rows)), \
             patch.object(arena, "rsi", return_value=[50.0]*len(rows)), \
             patch.object(arena, "zscore", return_value=0.0):
            result=backtest(rows)
        self.assertGreater(result["trades"], 0)
        self.assertAlmostEqual(result["trade_log"][0]["entry"], rows[56]["o"])

    def test_short_history_safe(self):
        rows=[{"ts":i,"o":100,"h":101,"l":99,"c":100,"v":100} for i in range(20)]
        r=backtest(rows)
        self.assertEqual(r["trades"],0)

if __name__=="__main__": unittest.main()
