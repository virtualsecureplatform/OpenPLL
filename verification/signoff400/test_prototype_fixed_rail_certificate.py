import unittest
from fractions import Fraction as F
from replay_prototype_fixed_rail_certificate import replay

FIXED='__fixed_rail_AC_reference'


class FixedRailCertificateControls(unittest.TestCase):
    def test_negative_ground_cap_can_have_positive_network_energy(self):
        # C=[[1,-2],[-2,5]]: energy=(Va-2Vb)^2+Vb^2 > 0.
        pairs=[('a','b',F(2)),('a',FIXED,F(-1)),('b',FIXED,F(3))]
        self.assertEqual(replay(pairs,{'a':9,'b':4}),{'a':F(1),'b':F(2)})
        self.assertLess(replay(pairs,{'a':1,'b':1})['a'],0)

    def test_indefinite_network_cannot_pass_the_inequalities(self):
        pairs=[('a','b',F(2)),('a',FIXED,F(-3)),('b',FIXED,F(3))]
        for weights in ({'a':1,'b':1},{'a':9,'b':4}):
            self.assertLess(replay(pairs,weights)['a'],0)

    def test_incomplete_nonpositive_boolean_weights_and_duplicate_pairs_rejected(self):
        pairs=[('a',FIXED,F(1))]
        for weights in ({},{'a':0},{'a':True},{'a':1,'extra':1}):
            with self.assertRaises(ValueError):replay(pairs,weights)
        with self.assertRaises(ValueError):replay(pairs+pairs,{'a':1})


if __name__=='__main__':unittest.main()
