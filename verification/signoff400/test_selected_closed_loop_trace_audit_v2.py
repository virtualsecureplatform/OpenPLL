import csv,json,tempfile,unittest
from pathlib import Path
from common_v3 import PROFILE,sha
from audit_selected_closed_loop_traces_v2 import case_traces
from selected_reference_phase import assess

class ClosedLoopTraceAuditTest(unittest.TestCase):
    def fixture(self,root,period=2.5):
        directory=root/'cold_start_phase0';directory.mkdir()
        with (directory/'edges.csv').open('w') as f:
            writer=csv.writer(f);writer.writerow(['event','time_ns','code','bbpd'])
            for kind,step,last in [('REF',40,220010),('DIV',40,220000),('OUT',period,220000)]:
                for index in range(int((last-10)//step)+1):writer.writerow([kind,10+index*step,111,0])
        (directory/'controls.csv').write_text('event,time_ps,fine\nTUNE,0,111\n')
        (directory/'segments.csv').write_text('segment,enabled_ns,stop_ns\n0,0,220000\n')
        (directory/'run.log').write_text('REFERENCE_PHASE_INITIALIZED epoch=0 feedback_ns=10.000 reference_ns=10.000 offset_ns=0\nPROGRAMMED400_LOOP_END scenario=0\n')
        receipt=dict(artifacts={str(p):sha(p) for p in directory.iterdir()})
        case=dict(scenario='cold_start',phase_offset_ns=0,native_exit=0,passed=True,
                  reference_phase_initializations=assess(directory,0,0)['initializations'])
        return receipt,case

    def test_real_limits_recomputed_for_passing_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            r,c=self.fixture(Path(folder));self.assertTrue(case_traces(r,c,json.loads(PROFILE.read_text())))

    def test_forged_pass_does_not_override_wrong_frequency(self):
        with tempfile.TemporaryDirectory() as folder:
            r,c=self.fixture(Path(folder),2.0)
            with self.assertRaisesRegex(ValueError,'fails functional limits'):case_traces(r,c,json.loads(PROFILE.read_text()))

    def test_unpinned_control_and_forged_phase_coordinates_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            r,c=self.fixture(Path(folder));profile=json.loads(PROFILE.read_text())
            c['reference_phase_initializations'][0]['reference_ns']=11
            with self.assertRaisesRegex(ValueError,'coordinates differ'):case_traces(r,c,profile)
            del r['artifacts'][str(Path(folder)/'cold_start_phase0/controls.csv')]
            with self.assertRaisesRegex(ValueError,'must be pinned'):case_traces(r,c,profile)

    def test_campaign_auditor_rejects_pass_flags_without_raw_traces(self):
        from audit_prototype_v4 import audit,CHECKS
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.write_text('fixture')
            pins={str(source):sha(source)};candidate=dict(source_sha256=pins,physical_sha256=pins)
            profile=json.loads(PROFILE.read_text());records=[]
            for scenario in profile['scenarios']:
                for phase in profile['reference_phase_offsets_ns']:
                    count=1 if scenario=='cold_start' else 2
                    records.append(dict(scenario=scenario,phase_offset_ns=phase,passed=True,native_exit=0,
                        reference_phase_coverage_pass=True,reference_phase_initializations=[
                            dict(epoch=i,feedback_ns=100.,reference_ns=100.+phase,measured_offset_ns=phase) for i in range(count)]))
            receipt=root/'receipt.json'
            receipt.write_text(json.dumps(dict(status='pass',profile_sha256=sha(PROFILE),candidate=candidate,
                input_sha256=pins,artifacts=pins,gate='closed_loop_operation',validated_for_prototype=True,
                checks={key:True for key in CHECKS['closed_loop_operation']},corner='tt',temperature_c=27,
                supply_v=1.8,ki=4,kp=0,records=records)))
            result=audit(dict(candidate=candidate,evidence={'closed_loop_operation':[dict(path=str(receipt),sha256=sha(receipt))]}))
            self.assertIn('one pinned raw edge trace per closed-loop case required',result['gates']['closed_loop_operation']['failures'])
            self.assertFalse(result['release_ready'])

    def test_exact_phase_limit_and_forged_real_excess(self):
        for span,passing in [(0.25,True),(0.251,False),(0.250001,False)]:
            with tempfile.TemporaryDirectory()as folder:
                root=Path(folder);receipt,case=self.fixture(root)
                path=root/'cold_start_phase0/edges.csv'
                with path.open()as stream:rows=list(csv.DictReader(stream))
                index=0
                for row in rows:
                    if row['event']=='DIV':
                        if index%2:row['time_ns']=str(float(row['time_ns'])+span)
                        index+=1
                with path.open('w')as f:
                    writer=csv.DictWriter(f,fieldnames=['event','time_ns','code','bbpd']);writer.writeheader();writer.writerows(rows)
                receipt['artifacts'][str(path)]=sha(path)
                if passing:self.assertTrue(case_traces(receipt,case,json.loads(PROFILE.read_text())))
                else:
                    with self.assertRaisesRegex(ValueError,'fails functional limits'):
                        case_traces(receipt,case,json.loads(PROFILE.read_text()))

if __name__=='__main__':unittest.main()
