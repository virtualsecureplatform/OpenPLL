import json
import unittest
from common_v3 import PROFILE
from review_prototype_common_gain_diagnostic import window_pass

class CommonGainWindows(unittest.TestCase):
    def test_direct_limits_reject_a_green_label_with_bad_data(self):
        p=json.loads(PROFILE.read_text())
        good=dict(frequency_error_ppm=999,phase_span_ns=.249,phase_mean_ns=-.249,phase_drift_ns=.049,
             cycle_slip=False,cycle_gaps=dict(REF=False,DIV=False,OUT=False),fine_outside_operating_range=False,
             fine_min=8,fine_max=247,passed=True)
        self.assertTrue(window_pass(good,p))
        for key,value in [('frequency_error_ppm',1001),('phase_span_ns',.251),('phase_mean_ns',-.251),
                          ('phase_drift_ns',-.051),('fine_min',7),('cycle_slip',True)]:
            self.assertFalse(window_pass(dict(good,**{key:value}),p),key)

if __name__=='__main__':unittest.main()
