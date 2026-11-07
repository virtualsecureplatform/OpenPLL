import csv,json,tempfile,unittest
from pathlib import Path
from common_v3 import save,sha,spec
from acceptance_v4 import evaluate
from selected_reference_phase import assess as phase_assess
from review_selected_frequency_stress_traces import recompute

class TraceReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.case=Path(self.temp.name);events={k:[]for k in ['REF','DIV','OUT']}
        events['OUT']=[[i*2.5,149,0]for i in range(88041)]
        for kind in ['REF','DIV']:events[kind]=[[20+i*40,149,0]for i in range(5504)]
        with(self.case/'edges.csv').open('w')as f:
            w=csv.writer(f);w.writerow(['event','time_ns','code','bbpd'])
            for kind in events:
                for row in events[kind]:w.writerow([kind,*row])
        (self.case/'controls.csv').write_text('event,time_ps,fine\nTUNE,0,149\n');(self.case/'segments.csv').write_text('segment,enabled_ns,stop_ns\n0,101,220101\n');(self.case/'run.log').write_text('REFERENCE_PHASE_INITIALIZED epoch=0 feedback_ns=140 reference_ns=140 offset_ns=0\nPROGRAMMED400_LOOP_END scenario=0\n')
        result=evaluate(events,[[0,149]],400,101,220101,spec());self.assertTrue(result['passed']);save(self.case/'segment0_acceptance.json',result);save(self.case/'reference_phase.json',phase_assess(self.case,0,0));save(self.case/'assessment.json',dict(native_exit=0,terminal_marker_present=True,measurement_requests=[],functional_trace_pass=True,state='diagnostic_simulation_completed'))
    def test_valid_trace_review_is_read_only(self):
        before={p.name:sha(p)for p in self.case.iterdir()};passed,segments=recompute(self.case,0,0);self.assertTrue(passed);self.assertEqual(len(segments),1);self.assertEqual(before,{p.name:sha(p)for p in self.case.iterdir()})
    def test_changed_saved_metric_rejected(self):
        p=self.case/'segment0_acceptance.json';r=json.loads(p.read_text());r['windows'][-1]['phase_span_ns']+=.001;save(p,r)
        with self.assertRaisesRegex(ValueError,'segment metrics differ'):recompute(self.case,0,0)
    def test_missing_actual_completion_marker_rejected(self):
        (self.case/'run.log').write_text('incomplete\n')
        with self.assertRaisesRegex(ValueError,'completion marker'):recompute(self.case,0,0)
    def test_changed_phase_evidence_rejected(self):
        p=self.case/'reference_phase.json';r=json.loads(p.read_text());r['initializations'][0]['measured_offset_ns']=1;save(p,r)
        with self.assertRaisesRegex(ValueError,'reference-phase'):recompute(self.case,0,0)
if __name__=='__main__':unittest.main()
