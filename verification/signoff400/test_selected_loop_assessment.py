import tempfile,unittest
from pathlib import Path
from selected_loop_assessment import assess

class LoopAssessmentTests(unittest.TestCase):
    def test_zero_exit_without_terminal_marker_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'run.log').write_text('partial run')
            self.assertFalse(assess(p,0,0)['functional_trace_pass'])
    def test_marker_for_another_scenario_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'run.log').write_text('PROGRAMMED400_LOOP_END scenario=1')
            self.assertFalse(assess(p,0,0)['functional_trace_pass'])
    def test_missing_second_segment_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'run.log').write_text('PROGRAMMED400_LOOP_END scenario=1')
            (p/'edges.csv').write_text('event,time_ns,code,bbpd\n')
            (p/'controls.csv').write_text('event,time_ps,fine\n')
            (p/'segments.csv').write_text('segment,enabled_ns,stop_ns\n0,0,220000\n')
            r=assess(p,0,1);self.assertFalse(r['functional_trace_pass']);self.assertIn('segments',r['failure'])

    def test_complete_functional_trace_passes_but_never_qualifies_release(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'run.log').write_text('PROGRAMMED400_LOOP_END scenario=0')
            with (p/'edges.csv').open('w') as f:
                f.write('event,time_ns,code,bbpd\n')
                for kind,step in [('REF',40),('DIV',40),('OUT',2.5)]:
                    for i in range(int(220080/step)+1):f.write(f'{kind},{i*step},111,0\n')
            (p/'controls.csv').write_text('event,time_ps,fine\nTUNE,0,111\n')
            (p/'segments.csv').write_text('segment,enabled_ns,stop_ns\n0,0,220000\n')
            r=assess(p,0,0)
            self.assertTrue(r['functional_trace_pass'])
            self.assertFalse(r['physical_models_qualified']);self.assertFalse(r['release_ready'])

if __name__=='__main__':unittest.main()
