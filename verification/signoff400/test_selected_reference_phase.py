import tempfile,unittest
from pathlib import Path
from selected_reference_phase import assess

class ReferencePhaseTests(unittest.TestCase):
    def fixture(self,p,phase):
        (p/'run.log').write_text(f'REFERENCE_PHASE_INITIALIZED epoch=0 feedback_ns=100 reference_ns={100+phase} offset_ns={phase}\n')
        (p/'edges.csv').write_text(f'event,time_ns,code,bbpd\nDIV,100,111,0\nREF,{100+phase},111,0\n')
        (p/'segments.csv').write_text('segment,enabled_ns,stop_ns\n0,0,220000\n')
    def test_recorded_edges_prove_requested_phase(self):
        for phase in [0,10,20,30]:
            with self.subTest(phase=phase),tempfile.TemporaryDirectory() as d:
                p=Path(d);self.fixture(p,phase);self.assertTrue(assess(p,0,phase)['reference_phase_coverage_pass'])
    def test_collapsed_or_unrecorded_phase_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p,0);self.assertFalse(assess(p,0,10)['reference_phase_coverage_pass'])
            self.fixture(p,10);(p/'edges.csv').write_text('event,time_ns,code,bbpd\nDIV,100,111,0\nREF,100,111,0\n')
            self.assertFalse(assess(p,0,10)['reference_phase_coverage_pass'])
    def test_second_scenario_epoch_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p,10);self.assertFalse(assess(p,1,10)['reference_phase_coverage_pass'])

class ReferencePhaseReleaseGateTests(unittest.TestCase):
    def test_passing_case_labels_without_phase_evidence_are_rejected(self):
        import json
        from audit_prototype_v3 import audit,CHECKS,PROFILE
        from common import sha
        profile=json.loads(PROFILE.read_text())
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'source';source.write_text('test-only evidence fixture')
            candidate=dict(source_sha256={str(source):sha(source)},physical_sha256={str(source):sha(source)})
            receipt=p/'claim.json'
            value=dict(status='pass',profile_sha256=sha(PROFILE),candidate=candidate,
                input_sha256={str(source):sha(source)},artifacts={str(source):sha(source)},
                gate='closed_loop_operation',validated_for_prototype=True,
                checks={key:True for key in CHECKS['closed_loop_operation']},
                corner='tt',temperature_c=27,supply_v=1.8,ki=4,kp=0,
                records=[dict(scenario=scenario,phase_offset_ns=phase,passed=True)
                         for scenario in profile['scenarios'] for phase in profile['reference_phase_offsets_ns']])
            receipt.write_text(json.dumps(value))
            result=audit(dict(candidate=candidate,evidence={'closed_loop_operation':[dict(path=str(receipt),sha256=sha(receipt))]}))
            self.assertIn('reference phase coverage not demonstrated',result['gates']['closed_loop_operation']['failures'])
            self.assertFalse(result['release_ready'])
            for case in value['records']:case['reference_phase_coverage_pass']=True
            receipt.write_text(json.dumps(value))
            result=audit(dict(candidate=candidate,evidence={'closed_loop_operation':[dict(path=str(receipt),sha256=sha(receipt))]}))
            self.assertIn('incomplete phase coordinate evidence',result['gates']['closed_loop_operation']['failures'])

if __name__=='__main__':unittest.main()
