import unittest
import numpy as np
from measure_keeper_clock_buffer_input_charge import integral,observe


class InputChargeMeasurements(unittest.TestCase):
    def test_clipped_integral_on_nonuniform_samples(self):
        t=np.array([0.,.1,.4,.9,1.])
        self.assertAlmostEqual(integral(t,2*t,.2,.8),.8**2-.2**2)
        with self.assertRaises(ValueError):integral(t,t,-.1,.8)

    def test_reference_capacitor_sign_and_units(self):
        t=np.array([0,9.8,9.9,10,10.1,10.2,34])*1e-9
        current=np.full(len(t),-20e-15*1.8/400e-12)
        cap=-integral(t,current,9.88e-9,10.12e-9)/1.08
        self.assertAlmostEqual(cap/20e-15,1.,places=12)

    def test_inverting_or_unsettled_output_cannot_pass_buffer_response(self):
        t=np.linspace(0,34e-9,17001)
        v=np.where((t>=10e-9)&(t<22e-9),1.8,0.)
        i=np.zeros(len(t))
        self.assertTrue(observe(t,v,i,v,400)['noninverting_response_verified'])
        self.assertFalse(observe(t,v,i,1.8-v,400)['noninverting_response_verified'])
        self.assertFalse(observe(t,v,i,np.full(len(t),.9),400)['noninverting_response_verified'])


if __name__=='__main__':
    unittest.main()
