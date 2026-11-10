import unittest
from contact_capture_settling_v2 import assess_settling

class SettlingScreen(unittest.TestCase):
    def trace(self,drift=False):
        rows=[]
        for i in range(2721):
            t=i*.125
            phase=t/2.5 if not drift or t<300 else 120+(t-300)/2.6
            rows.append([t*1e-9,1.8 if phase%1>=.5 else 0.])
        return rows
    def test_stationary_sample_passes_without_qualification(self):
        r=assess_settling(self.trace());self.assertTrue(r['sample_stability_screen_pass'])
        self.assertFalse(r['physical_settling_qualified']);self.assertEqual(len(r['windows']),6)
    def test_drift_and_missing_edges_do_not_pass(self):
        self.assertFalse(assess_settling(self.trace(True))['sample_stability_screen_pass'])
        self.assertFalse(assess_settling([[0,0],[340e-9,0]])['sample_stability_screen_pass'])
    def test_truncation_and_duplicate_times_rejected(self):
        rows=self.trace()
        for invalid in [rows[:-1],rows+[rows[-1]]]:
            with self.assertRaises(ValueError):assess_settling(invalid)

if __name__=='__main__':unittest.main()
