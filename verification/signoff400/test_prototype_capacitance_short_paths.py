import unittest
from fractions import Fraction as F
from check_prototype_capacitance_short_paths import certify


class ShortPaths(unittest.TestCase):
    def verify_witnesses(self,pairs,result):
        loads={}
        for w in result['witnesses']:
            a,b=w['negative_pair'];node=a;resistance=F()
            for edge in w['positive_path']:
                self.assertIn(node,edge);node=edge[1] if edge[0]==node else edge[0]
                value=pairs[tuple(edge)];self.assertGreater(value,0);resistance+=1/value
            self.assertEqual(node,b)
            ratio=F(w['negative_magnitude_F'])*resistance
            self.assertEqual(ratio,F(w['allocated_fraction']))
            for edge in w['positive_path']:
                key=tuple(edge);loads[key]=loads.get(key,F())+ratio
        self.assertEqual(result['passivity_certified'],all(v<=1 for v in loads.values()))

    def test_local_and_longer_path_witnesses_recompute_exactly(self):
        for p in [{('a','b'):F(-1,10),('a','g'):F(1),('b','g'):F(1)},
                  {('a','d'):F(-1,10),('a','b'):F(1),('b','c'):F(1),('c','d'):F(1)}]:
            r=certify(p);self.assertTrue(r['passivity_certified']);self.verify_witnesses(p,r)

    def test_shared_edge_overallocation_and_disconnected_compensation_rejected(self):
        p={('a','b'):F(-1),('a','g'):F(1),('b','g'):F(1)}
        r=certify(p);self.assertFalse(r['passivity_certified']);self.verify_witnesses(p,r)
        self.assertFalse(certify({('a','b'):F(-1)})['passivity_certified'])


if __name__=='__main__':unittest.main()
