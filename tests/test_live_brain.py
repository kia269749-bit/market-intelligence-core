import unittest
from mi_core.live_brain import _market_bias

class LiveBrainTests(unittest.TestCase):
    def test_neutral_without_change_data(self):
        bias,confidence=_market_bias({"rows":[]})
        self.assertEqual(bias,"NEUTRAL")
        self.assertEqual(confidence,.25)

if __name__=="__main__": unittest.main()
