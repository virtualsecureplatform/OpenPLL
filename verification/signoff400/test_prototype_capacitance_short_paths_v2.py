import unittest
from fractions import Fraction as F
from check_prototype_capacitance_short_paths_v2 import certify


class DiagonalScreen(unittest.TestCase):
    def test_exact_negative_coordinate_energy_is_rejected(self):
        p={('a','g'):F(-2),('a','b'):F(1),('b','g'):F(3)}
        r=certify(p)
        self.assertFalse(r['passivity_certified'])
        w=next(w for w in r['negative_diagonal_witnesses'] if w['node']=='a')
        self.assertEqual(F(w['energy_F']),sum(c for edge,c in p.items() if 'a' in edge))
        self.assertEqual(F(w['energy_F']),-1)

    def test_nonnegative_diagonals_still_require_a_complete_path_certificate(self):
        p={('a','b'):F(-1,10),('a','g'):F(1),('b','g'):F(1)}
        r=certify(p)
        self.assertTrue(r['passivity_certified'])
        self.assertEqual(len(r['witnesses']),1)
        self.assertEqual(F(r['witnesses'][0]['allocated_fraction']),F(1,5))


if __name__=='__main__':unittest.main()
