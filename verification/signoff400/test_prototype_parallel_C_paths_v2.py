import copy,json
from fractions import Fraction as F
import unittest
from certify_prototype_parallel_C_paths_v2 import certificate,replay,lower,summary


class BoundedParallelPaths(unittest.TestCase):
    def network(self):return {('a','b'):F(-3,5),('a','x'):F(1),('b','x'):F(1),('a','y'):F(1),('b','y'):F(1)}

    def test_conservative_capacity_enclosures_and_exact_replay(self):
        for v in (F(1,10),F(1,4),F(137,999999)):
            self.assertLessEqual(lower(v),v)
        p=self.network();r=certificate(p);self.assertTrue(r['passivity_certified'])
        self.assertTrue(replay(p,r)['all_negative_pairs_covered'])
        bad=copy.deepcopy(r);bad['witnesses'][0]['paths'][0]['covered_negative_C_lower_F']='100'
        with self.assertRaises(ValueError):replay(p,bad)

    def test_failure_diagnostic_handles_huge_rationals_without_relaxing_integer_limits(self):
        r=summary(F(1,10**5000+7));json.dumps(r)
        self.assertGreater(r['denominator_bits'],10000)
        self.assertFalse(r['exact_value_claimed'])
        p=self.network();p['a','b']=F(-2)
        self.assertFalse(certificate(p)['passivity_certified'])


if __name__=='__main__':unittest.main()
