from fractions import Fraction as F
import unittest
from bounded_C_diagonal_guard import coefficient,review


class DiagonalGuard(unittest.TestCase):
    def test_exact_guard_restores_a_psd_source_under_symmetric_export_error(self):
        # PSD source [[1,-1],[-1,1]], perturbed off diagonals by -epsilon.
        e=F(1,10000);diagonal=1+e;off=-1-e
        self.assertEqual(diagonal*diagonal-off*off,0)
        self.assertLess(F(1)-off*off,0)
        report=review({'a':e,'b':e},{'a':1,'b':1},{'a':e/10**15,'b':e/10**15},set(),F(1,1000))
        self.assertTrue(report['symmetric_row_error_domination_verified'])

    def test_emitted_coefficient_is_an_exact_upper_enclosure(self):
        error=F(1,3*10**9);text,value=coefficient(error)
        self.assertEqual(value,F(text));self.assertGreaterEqual(value*10**15,error)
        with self.assertRaises(ValueError):review({'a':error},{'a':1},{'a':0},set(),F(1,1000))
        with self.assertRaises(ValueError):review({'a':1},{'a':1},{'a':F(1,10**15)},set(),F(1,1000))


if __name__=='__main__':unittest.main()
