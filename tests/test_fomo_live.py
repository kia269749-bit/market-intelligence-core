import unittest
from mi_core.fomo_live import _score_pair

class FomoLiveTests(unittest.TestCase):
    def test_score_is_bounded(self):
        row={"liquidity":{"usd":1000000},"volume":{"h24":5000000},
             "priceChange":{"h24":20},"txns":{"h24":{"buys":100,"sells":20}}}
        self.assertGreaterEqual(_score_pair(row),0)
        self.assertLessEqual(_score_pair(row),100)

if __name__=="__main__": unittest.main()
