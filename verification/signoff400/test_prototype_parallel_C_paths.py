import copy
from fractions import Fraction as F
import unittest
from certify_prototype_parallel_C_paths import certificate,replay


class ParallelPaths(unittest.TestCase):
    def network(self):return {('a','b'):F(-3,5),('a','x'):F(1),('b','x'):F(1),('a','y'):F(1),('b','y'):F(1)}

    def test_parallel_paths_certify_a_pair_that_no_single_path_can_cover(self):
        p=self.network();r=certificate(p)
        self.assertTrue(r['passivity_certified']);self.assertEqual(len(r['witnesses'][0]['paths']),2)
        self.assertTrue(replay(p,r)['all_negative_pairs_covered'])

    def test_uncovered_negative_energy_is_not_certified(self):
        p=self.network();p['a','b']=F(-2)
        self.assertFalse(certificate(p)['passivity_certified'])
        self.assertFalse(certificate({('a','b'):F(-1)})['passivity_certified'])

    def test_independent_replay_rejects_changed_path_capacity_and_omitted_pair(self):
        p=self.network();r=certificate(p);changed=copy.deepcopy(r)
        changed['witnesses'][0]['paths'][0]['edges'][0]['fraction']='0'
        with self.assertRaises(ValueError):replay(p,changed)
        changed=copy.deepcopy(r);changed['witnesses']=[]
        with self.assertRaises(ValueError):replay(p,changed)


if __name__=='__main__':unittest.main()
