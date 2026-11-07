import unittest
from selected_gain_screen_disposition import classify

class Disposition(unittest.TestCase):
    def base(self):return dict(state='diagnostic_simulation_completed',native_exit=0,terminal_marker_present=True,reference_phase_coverage_pass=True,functional_trace_pass=True,measurement_requests=[])
    def test_pass(self):self.assertEqual(classify(self.base()),'pass_screen')
    def test_covered_failure(self):self.assertEqual(classify(dict(self.base(),state='diagnostic_failed',functional_trace_pass=False)),'functional_failure')
    def test_missing_lookup_indeterminate(self):self.assertEqual(classify(dict(self.base(),state='needs_native_tuning_points',measurement_requests=[dict(coarse=20,fine=182)])),'indeterminate_lookup')
    def test_incomplete_or_wrong_phase_never_gain_failure(self):
        for field,value in [('native_exit',1),('terminal_marker_present',False),('reference_phase_coverage_pass',False)]:
            with self.assertRaisesRegex(ValueError,'gain rejection forbidden'):classify(dict(self.base(),state='diagnostic_failed',functional_trace_pass=False,**{field:value}))
    def test_inconsistent_state_rejected(self):
        with self.assertRaises(ValueError):classify(dict(self.base(),state='diagnostic_failed'))
    def test_lookup_state_needs_requests(self):
        with self.assertRaises(ValueError):classify(dict(self.base(),state='needs_native_tuning_points'))
if __name__=='__main__':unittest.main()
