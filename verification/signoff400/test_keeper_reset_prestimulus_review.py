import unittest
import numpy as np
from review_keeper_reset_prestimulus_windows import reassess


class PrestimulusWindow(unittest.TestCase):
    def fixture(self):
        t=np.linspace(0,22e-9,11001)
        q=np.where((t>=8.5e-9)&(t<10e-9),1.8,0.)
        control=np.where((t>=9.2e-9)&(t<=12.8e-9),0.,1.8)
        case=dict(full_ramp_ps=1600,reset_state=0,negative_control=False)
        return t,q,control,case

    def test_window_is_before_ramp_and_after_settling(self):
        t,q,c,case=self.fixture()
        r=reassess(t,q,c,case)
        self.assertFalse(r['original_prestate_verified'])
        self.assertTrue(r['fixture_passed'])
        self.assertLess(r['prestimulus_window_ns'][1],r['ramp_leading_ns'])

    def test_after_ramp_state_cannot_establish_prestate(self):
        t,q,c,case=self.fixture()
        q[:]=0
        q[(t>=9.3e-9)&(t<10e-9)]=1.8
        self.assertFalse(reassess(t,q,c,case)['fixture_passed'])

    def test_window_must_be_inactive_and_adequately_sampled(self):
        t,q,c,case=self.fixture()
        c[(t>=9e-9)&(t<=9.1e-9)]=0
        with self.assertRaises(ValueError):reassess(t,q,c,case)
        with self.assertRaises(ValueError):reassess(t[::100],q[::100],c[::100],case)


if __name__ == '__main__':
    unittest.main()
