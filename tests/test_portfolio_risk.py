import unittest
from mi_core.portfolio_risk import PositionCandidate, PortfolioRiskConfig, regime_multiplier, position_risk_fraction, portfolio_risk_gate

class PortfolioRiskTests(unittest.TestCase):
    def test_regime_multiplier(self):
        self.assertEqual(regime_multiplier("BULL"), 1.0)
        self.assertLess(regime_multiplier("HIGH_VOL"), 1.0)

    def test_position_sizing_is_capped(self):
        q=PositionCandidate("BTC", .9, .2, .9, .02, "BULL")
        self.assertLessEqual(position_risk_fraction(q), .02)
        q2=PositionCandidate("BTC", .9, .2, .9, .02, "HIGH_VOL")
        self.assertLess(position_risk_fraction(q2), position_risk_fraction(q))

    def test_portfolio_gate(self):
        result=portfolio_risk_gate([.02,.02], .01)
        self.assertTrue(result["eligible"])
        result=portfolio_risk_gate([.04,.04])
        self.assertFalse(result["eligible"])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            position_risk_fraction(PositionCandidate("BTC", 1.1, 0, 1, .02, "BULL"))
        with self.assertRaises(ValueError):
            position_risk_fraction(PositionCandidate("BTC", .5, 0, .5, 0, "BULL"))

if __name__=="__main__":
    unittest.main()
