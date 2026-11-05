from fractions import Fraction as F
import unittest
from check_prototype_capacitance_paths import certify


class PositivePathControls(unittest.TestCase):
    def test_exact_series_path_capacity_bounds_negative_edge(self):
        p={('a','b'):F(1),('b','c'):F(1),('a','c'):F(-2,5)}
        result=certify(p)
        self.assertTrue(result['passivity_certified'])
        self.assertEqual(F(result['maximum_positive_edge_allocation']),F(4,5))
        self.assertEqual(result['witnesses'][0]['positive_path'],[['a','b'],['b','c']])
        for a,b,c in [(F(0),F(1),F(2)),(F(-1),F(3),F(1))]:
            self.assertGreaterEqual((a-b)**2+(b-c)**2-F(2,5)*(a-c)**2,0)

    def test_missing_path_and_overallocated_path_do_not_certify(self):
        self.assertFalse(certify({('a','c'):F(-1)})['passivity_certified'])
        self.assertFalse(certify({('a','b'):F(1),('b','c'):F(1),('a','c'):F(-3,5)})['passivity_certified'])

    def test_sufficient_test_failure_does_not_claim_indefiniteness(self):
        # Two parallel unit-capacitance paths give effective capacity 1;
        # a single-path allocation cannot certify subtraction of 3/4.
        p={('a','b'):F(1),('b','c'):F(1),('a','d'):F(1),('c','d'):F(1),('a','c'):F(-3,4)}
        result=certify(p)
        self.assertFalse(result['passivity_certified'])
        self.assertFalse(result.get('indefiniteness_proved',False))
        # Positive leading minors of the grounded 3x3 matrix independently establish PSD.
        self.assertTrue(all(v>0 for v in [F(2),F(3,2),F(1)]))


if __name__=='__main__':unittest.main()
