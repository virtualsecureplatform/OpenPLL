import unittest
import numpy as np
from prepare_selected_replay_prefix import prefix

class PrefixTests(unittest.TestCase):
    def test_right_guard_knot_retained(self):
        rows=['0 0\n','1e-11 1\n','2e-11 0\n'];self.assertEqual(prefix(rows,1e-15),rows[:2])
    def test_voltage_is_exact_over_declared_interval(self):
        rows=['0 0.25\n','1e-11 1.25\n','2e-11 -1\n'];p=prefix(rows,1e-15)
        a=np.asarray([list(map(float,l.split())) for l in rows]);b=np.asarray([list(map(float,l.split())) for l in p]);t=np.linspace(0,1e-15,23)
        np.testing.assert_array_equal(np.interp(t,a[:,0],a[:,1]),np.interp(t,b[:,0],b[:,1]))
    def test_missing_right_guard_rejected(self):
        with self.assertRaises(ValueError):prefix(['0 0\n'],1e-15)
    def test_missing_initial_state_rejected(self):
        with self.assertRaises(ValueError):prefix(['1e-12 0\n','2e-12 1\n'],1e-15)
    def test_nonfinite_voltage_rejected(self):
        with self.assertRaises(ValueError):prefix(['0 0\n','1e-11 nan\n'],1e-15)

if __name__=='__main__':unittest.main()
