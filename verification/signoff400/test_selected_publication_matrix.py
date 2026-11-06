import unittest
from follow_selected_publication_matrix import result_record

class MatrixResult(unittest.TestCase):
    def base(self):return dict(scenario=1,phase_offset_ns=20,diagnostic=True,physical_models_qualified=False,release_ready=False,state='diagnostic_simulation_completed',functional_trace_pass=True,reference_phase_coverage_pass=True,native_exit=0,terminal_marker_present=True,measurement_requests=[])
    def test_complete_actual_case_required_for_functional_pass(self):
        self.assertTrue(result_record(self.base(),1,20)['functional_trace_pass'])
        for key,value in [('state','needs_native_tuning_points'),('state','diagnostic_failed'),('native_exit',1),('terminal_marker_present',False),('reference_phase_coverage_pass',False)]:
            report=self.base();report[key]=value
            with self.subTest(key=key):self.assertFalse(result_record(report,1,20)['functional_trace_pass'])
    def test_wrong_phase_or_promoted_scope_rejected(self):
        for key,value in [('scenario',0),('phase_offset_ns',0),('physical_models_qualified',True),('release_ready',True),('diagnostic',False)]:
            report=self.base();report[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):result_record(report,1,20)

if __name__=='__main__':unittest.main()
