import unittest
import numpy as np
from fit_keeper_receiver_charge_surface import features,positive_fit


class PositiveChargeSurface(unittest.TestCase):
    def test_known_nonnegative_surface_recovered(self):
        rng=np.random.default_rng(42)
        v=rng.uniform(0,1.8,1000);mid=rng.uniform(0,1.8,1000)
        x=features(v,mid)
        expected=np.array([2.+.1*i for i in range(10)]+[.8])
        fitted,_=positive_fit(x,x@expected)
        self.assertTrue(np.all(fitted>=0))
        self.assertLess(float(np.max(abs(x@fitted-x@expected))),1e-6)

    def test_nonnegative_coefficients_give_monotone_input_charge(self):
        v=np.linspace(0,1.8,100)
        q=features(v,np.full(len(v),.9))@np.arange(1,12)
        self.assertTrue(np.all(np.diff(q)>=0))

    def test_nonfinite_or_unexercised_fit_rejected(self):
        with self.assertRaises(ValueError):features(np.array([float('nan')]),np.array([0.]))
        with self.assertRaises(ValueError):positive_fit(np.zeros((10,11)),np.zeros(10))


if __name__=='__main__':
    unittest.main()
