import unittest
import numpy as np
from assess_keeper_early_settling import measure
class EarlySettling(unittest.TestCase):
    def fixture(self):
        times=np.arange(521)*.5e-9;rows=np.column_stack((times,(np.arange(521)%2)*1.8));controls=np.column_stack((times,np.full(521,1.8)));controls[:3,1]=0
        return rows,controls,{'coarse':dict(bus='COARSETHERMAL_CODE',bit=0)}
    def test_window_diagnostics_do_not_qualify_short_capture(self):
        r,c,b=self.fixture();a=measure(r,c,b,1,0)
        self.assertEqual(a['last_mismatching_control_sample_ns'],1.)
        self.assertAlmostEqual(a['all_controls_match_from_saved_sample_ns'],1.5)
        self.assertTrue(all(x['all_physical_controls_match_at_all_saved_samples'] for x in a['windows']))
        self.assertTrue(all(abs(x['frequency_difference_from_final_ppm'])<1e-6 for x in a['windows']))
        self.assertFalse(a['shorter_native_capture_qualified'])
    def test_missing_early_oscillation_is_reported_without_losing_final_result(self):
        r,c,b=self.fixture();r[r[:,0]<80e-9,1]=0;a=measure(r,c,b,1,0)
        self.assertFalse(a['windows'][0]['frequency_available']);self.assertTrue(a['windows'][-1]['frequency_available'])
    def test_late_control_failure_is_exposed(self):
        r,c,b=self.fixture();c[-1,1]=0;a=measure(r,c,b,1,0)
        self.assertIsNone(a['all_controls_match_from_saved_sample_ns']);self.assertFalse(a['windows'][-1]['all_physical_controls_match_at_all_saved_samples'])
    def test_truncation_and_misaligned_grid_rejected(self):
        r,c,b=self.fixture()
        with self.assertRaises(ValueError):measure(r[:-1],c[:-1],b,1,0)
        c[1,0]+=.1e-9
        with self.assertRaises(ValueError):measure(r,c,b,1,0)
if __name__=='__main__':unittest.main()
