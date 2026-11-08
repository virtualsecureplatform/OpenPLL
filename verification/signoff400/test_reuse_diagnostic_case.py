import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from reuse_diagnostic_case import load_case


class CaseReuse(unittest.TestCase):
    def fixture(self,root):
        model=root/'model';model.write_text('frozen')
        arguments=dict(scenario=0,ki=1,kp=2,seed=128)
        inputs=root/'inputs.json';inputs.write_text(json.dumps(dict(case_arguments=arguments,frequency_table_kind='linear_frequency')))
        log=root/'run.log';log.write_text('completed')
        record=dict(input_sha256={str(inputs):sha(inputs),str(model):sha(model)},artifacts={str(log):sha(log)},
                    release_ready=False,diagnostic=True,state='diagnostic_simulation_completed',native_exit=0,
                    terminal_marker_present=True,reference_phase_coverage_pass=True,functional_trace_pass=True,
                    segments=[dict(segment=0,passed=True)],measurement_requests=[])
        receipt=root/'assessment.json';receipt.write_text(json.dumps(record))
        return receipt,arguments,model,record

    def test_completed_matching_case_can_be_reused(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,args,model,_=self.fixture(Path(d))
            self.assertTrue(load_case(receipt,args,{str(model):sha(model)})['functional_trace_pass'])

    def test_changed_parameters_or_model_identity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,args,model,_=self.fixture(Path(d))
            with self.assertRaises(ValueError):load_case(receipt,dict(args,kp=4),{str(model):sha(model)})
            with self.assertRaises(ValueError):load_case(receipt,args,{str(model):'different'})

    def test_infrastructure_failure_is_not_reused_as_gain_failure(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,args,model,record=self.fixture(Path(d));record['failure']='truncated trace'
            receipt.write_text(json.dumps(record))
            with self.assertRaises(ValueError):load_case(receipt,args,{str(model):sha(model)})

    def test_model_request_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,args,model,record=self.fixture(Path(d))
            record.update(state='needs_native_tuning_points',native_exit=1,terminal_marker_present=False,
                          functional_trace_pass=False,measurement_requests=[dict(coarse=23,fine=150)])
            receipt.write_text(json.dumps(record))
            self.assertEqual(load_case(receipt,args,{str(model):sha(model)})['state'],'needs_native_tuning_points')


if __name__=='__main__':unittest.main()
