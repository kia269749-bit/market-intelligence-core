import os, unittest
from unittest.mock import patch
from mi_core.fred_data import EconomicObservation, parse_observations, daily_returns, align_daily_series, fetch_series

class FredDataTests(unittest.TestCase):
    def test_parse_skips_missing(self):
        payload={"observations":[
            {"date":"2026-01-01","value":"100"},
            {"date":"2026-01-02","value":"."},
            {"date":"2026-01-03","value":"101.5"},
            {"date":"2026-01-04","value":"bad"},
        ]}
        rows=parse_observations(payload,"dxy")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0].series_id,"DXY")

    def test_returns_are_date_keyed(self):
        rows=[EconomicObservation("X","2026-01-01",100),
              EconomicObservation("X","2026-01-02",105),
              EconomicObservation("X","2026-01-03",102)]
        out=daily_returns(rows)
        self.assertAlmostEqual(out["2026-01-02"],.05)
        self.assertAlmostEqual(out["2026-01-03"],102/105-1)

    def test_alignment_does_not_forward_fill(self):
        rows=[EconomicObservation("A","2026-01-01",10),
              EconomicObservation("A","2026-01-02",11)]
        self.assertEqual(set(align_daily_series({"a":rows})["A"]),{"2026-01-02"})

    def test_key_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                fetch_series("DXY", api_key=None)

if __name__=="__main__":
    unittest.main()
