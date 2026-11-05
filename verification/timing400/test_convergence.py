"""Negative controls for the400MHz calibration gate using the actual assessor."""
import copy
import json
import unittest

from run_dco_qualification import REQUIREMENTS, assess


class ConvergenceControls(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads(REQUIREMENTS.read_text())
        baseline={code:dict(mhz=mhz,half_window_difference_mhz=.001)
                  for code,mhz in ((100,399.8),(101,400),(102,400.2))}
        self.samples={variant:copy.deepcopy(baseline) for variant in ('baseline','step','tolerance','settling')}

    def test_400mhz_cap_is_40khz(self):
        result=assess(self.samples,400,self.spec)
        self.assertTrue(result['convergence_passed'])
        self.assertTrue(all(abs(row['limit_mhz']-.04)<1e-12 for row in result['comparisons']))

    def test_tolerance_disagreement_cannot_pass(self):
        self.samples['tolerance'][101]['mhz']+=.041
        self.assertFalse(assess(self.samples,400,self.spec)['convergence_passed'])

    def test_long_duration_disagreement_cannot_pass(self):
        self.samples['settling'][101]['mhz']+=.041
        self.assertFalse(assess(self.samples,400,self.spec)['convergence_passed'])

    def test_quiet_cross_variant_agreement_does_not_hide_drift(self):
        self.samples['baseline'][101]['half_window_difference_mhz']=.05
        self.assertFalse(assess(self.samples,400,self.spec)['convergence_passed'])

    def test_missing_adjacent_codes_cannot_pass(self):
        for variant in self.samples:
            self.samples[variant]={code*2:sample for code,sample in self.samples[variant].items()}
        with self.assertRaises(ValueError):assess(self.samples,400,self.spec)


if __name__=='__main__':
    unittest.main()
