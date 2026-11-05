import unittest
from measure_prototype_reset_input_charge import clipped_integral


class ChargeTest(unittest.TestCase):
    def test_known_capacitor_on_irregular_samples(self):
        capacitance=20e-15;ramp=200e-12
        current=-capacitance*1.8/ramp
        times=[0.,17e-12,53e-12,117e-12,163e-12,200e-12]
        charge=sum(clipped_integral(a,b,current,current,.2*ramp,.8*ramp)
                   for a,b in zip(times,times[1:]))
        self.assertAlmostEqual(-charge/1.08/capacitance,1.,places=12)

    def test_clipped_linear_current_and_nonmonotonic_samples(self):
        self.assertAlmostEqual(clipped_integral(0,4,0,4,1,3),4.)
        self.assertEqual(clipped_integral(0,1,2,3,2,3),0.)
        with self.assertRaises(ValueError):clipped_integral(1,1,0,0,0,2)


if __name__=='__main__':unittest.main()
