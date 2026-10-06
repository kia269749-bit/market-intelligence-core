import unittest
from mi_core.timing_engine import evaluate_entry_timing, evaluate_exit_timing

class TimingEngineTests(unittest.TestCase):
    def test_early_entry_is_detected(self):
        r=evaluate_entry_timing(confidence=.82,expected_move_pct=3.0,current_move_pct=.4,required_move_pct=1.15,agreement=.85,quality_score=1.0,regime="TREND")
        self.assertEqual(r["state"],"EARLY")
    def test_entry_becomes_late(self):
        r=evaluate_entry_timing(confidence=.90,expected_move_pct=3.0,current_move_pct=2.4,required_move_pct=1.15,agreement=.85,quality_score=1.0,regime="TREND")
        self.assertEqual(r["state"],"LATE")
    def test_two_exit_warnings_take_profit(self):
        r=evaluate_exit_timing(position_open=True,profit_pct=1.8,leader_exit=True,orderbook_deterioration=True)
        self.assertEqual(r["state"],"TAKE_PROFIT")
    def test_multiple_exit_warnings_exit(self):
        r=evaluate_exit_timing(position_open=True,profit_pct=2.2,momentum_score=-.5,leader_exit=True,orderbook_deterioration=True,tradeflow_deterioration=True,forecast_reversal=True)
        self.assertEqual(r["state"],"EXIT")
    def test_no_position(self):
        self.assertEqual(evaluate_exit_timing(position_open=False)["state"],"NO_POSITION")

if __name__=="__main__": unittest.main()
