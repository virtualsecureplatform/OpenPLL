import unittest,time
from fractions import Fraction as F
from exact_local_C_elimination_v2 import eliminate
from project_prototype_fixed_rail_C_v2 import FIXED

class ExactElimination(unittest.TestCase):
    def check(self,pairs):return eliminate(pairs,time.monotonic()+5)[0]
    def test_passive_singular(self):
        self.assertTrue(self.check({('a','b'):F(2)})['passivity_certified'])
    def test_coupled_negative_energy(self):
        p={('a','b'):F(-2),('a',FIXED):F(3),('b',FIXED):F(3)}
        r=self.check(p);self.assertTrue(r['indefiniteness_proved']);self.assertLess(F(r['exact_twice_energy_J']),0)
    def test_zero_pivot_with_off_diagonal(self):
        r=self.check({('a','b'):F(1),('a',FIXED):F(-1)})
        self.assertTrue(r['indefiniteness_proved'])
    def test_higher_order_indefiniteness(self):
        # Every two-node principal block is positive; the common three-node
        # voltage mode has negative energy.
        p={('a','b'):F(2),('b','c'):F(2),('a','c'):F(2),('a',FIXED):F(-1),('b',FIXED):F(-1),('c',FIXED):F(-1)}
        self.assertTrue(self.check(p)['indefiniteness_proved'])
    def test_bound_stays_inconclusive(self):
        r,_=eliminate({('a','b'):F(1)},time.monotonic()-1)
        self.assertFalse(r['conclusive'])

if __name__=='__main__':unittest.main()
