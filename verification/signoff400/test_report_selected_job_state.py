import json,tempfile,unittest
from pathlib import Path
from report_selected_job_state import inspect

class JobObservationTest(unittest.TestCase):
    def setup_case(self,root):
        p=Path(root);(p/'owner.json').write_text(json.dumps({'pid':123,'birth':'10'}));(p/'manifest.json').write_text('{}');(p/'status.json').write_text(json.dumps({'state':'real_driver_DCO_native_running'}));return p
    def test_queue_is_not_a_live_native_worker(self):
        with tempfile.TemporaryDirectory() as root:
            p=self.setup_case(root);probe=lambda pid:'10' if pid==123 else None
            self.assertEqual(inspect(p,{},probe)['observed_state'],'waiting_for_resources')
            self.assertEqual(inspect(p,None,probe)['observed_state'],'resource_admission_observation_pending')
            leases={'claim':{'pid':123,'birth':'10'}};self.assertEqual(inspect(p,leases,probe)['observed_state'],'starting_native_worker')
    def test_live_worker_overrides_stale_controller_status(self):
        with tempfile.TemporaryDirectory() as root:
            p=self.setup_case(root);(p/'native.process.json').write_text(json.dumps({'pid':456,'birth':'20'}));(p/'status.json').write_text('{"state":"stopped_without_qualification"}')
            self.assertEqual(inspect(p,{},lambda pid:{123:'10',456:'20'}.get(pid))['observed_state'],'native_worker_live')
    def test_reused_pid_and_transient_json(self):
        with tempfile.TemporaryDirectory() as root:
            p=self.setup_case(root);(p/'native.process.json').write_text(json.dumps({'pid':456,'birth':'20'}));probe=lambda pid:{123:'10',456:'21'}.get(pid)
            self.assertEqual(inspect(p,{},probe)['observed_state'],'native_worker_exited_controller_live')
            (p/'native.process.json').write_text('{');self.assertEqual(inspect(p,{},probe)['observed_state'],'observation_pending')

if __name__=='__main__':unittest.main()
