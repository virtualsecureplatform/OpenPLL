import unittest,math
import numpy as np
from compact_boundary_plateaus import compact_rows

class PlateauTests(unittest.TestCase):
    def test_constant_trace_keeps_both_endpoints(self):
        self.assertEqual(list(compact_rows([(0,1.8),(1,1.8),(2,1.8),(3,1.8)])),[(0,1.8),(3,1.8)])
    def test_transitions_and_interpolated_voltage_unchanged(self):
        original=[(0,0),(1,0),(2,0),(3,1),(4,1),(5,1),(6,-1),(7,-1),(8,-1)]
        compact=list(compact_rows(original));x=np.linspace(0,8,257)
        np.testing.assert_array_equal(np.interp(x,*zip(*original)),np.interp(x,*zip(*compact)))
    def test_nonconstant_knots_are_not_approximated(self):
        rows=[(0,0),(1,1e-20),(2,2e-20)];self.assertEqual(list(compact_rows(rows)),rows)
    def test_nonincreasing_times_rejected(self):
        with self.assertRaises(ValueError):list(compact_rows([(0,0),(1,1),(1,1)]))
        with self.assertRaises(ValueError):list(compact_rows([(0,0),(0,0)]))
    def test_nonfinite_values_rejected(self):
        with self.assertRaises(ValueError):list(compact_rows([(0,0),(1,float('nan'))]))

if __name__=='__main__':unittest.main()
