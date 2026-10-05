import unittest
from mi_core.fomo_normalizer import FomoTraderSnapshot
from mi_core.fomo_historical_ranker import historical_fomo_rank


class RankerTests(unittest.TestCase):
    def test_persistent_trader_is_ranked(self):
        rows=[]
        for i in range(3):
            rows.append(FomoTraderSnapshot('7d',i+1,'u1','alpha','Alpha',100+i,1000+i*100,50000,20+i,5,2,1,True))
        result=historical_fomo_rank(rows,min_snapshots=3)
        self.assertEqual(result[0]['trader_id'],'u1'); self.assertEqual(result[0]['snapshots'],3)

    def test_insufficient_history_is_excluded(self):
        row=FomoTraderSnapshot('7d',1,'u1','alpha','Alpha',100,1000,50000,20,5,2,1,True)
        self.assertEqual(historical_fomo_rank([row],min_snapshots=3),[])

if __name__=='__main__': unittest.main()