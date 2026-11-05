import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from run_selected_detector_phase_probe_v2 import reuse_snapshot

class DetectorSnapshotReuseTests(unittest.TestCase):
    def fixture(self,root):
        physical=root/'model';physical.write_text('physical candidate')
        raw=root/'unavailable_reference.raw'
        snapshot=root/'exterior_initial_voltages.json';snapshot.write_text(json.dumps({'n':1.8}))
        pins={str(physical):sha(physical),str(raw):'a'*64,str(snapshot):sha(snapshot)}
        (root/'manifest.json').write_text(json.dumps(dict(input_sha256=pins)))
        (root/'assessment.json').write_text(json.dumps(dict(native_exit_zero=True,input_sha256=pins)))
        (root/'status.json').write_text(json.dumps(dict(state='conditional_detector_probe_completed_assessment_pending')))
        return physical,raw,snapshot
    def test_reuses_completed_snapshot_without_reading_original_raw(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);model,raw,_=self.fixture(p)
            values,pins,digest=reuse_snapshot(p,[model],raw,['n'])
            self.assertEqual(values,{'n':1.8});self.assertEqual(digest,'a'*64)
            self.assertNotIn(str(raw),pins)
    def test_changed_physical_model_or_snapshot_is_rejected(self):
        for target in ['model','snapshot']:
            with self.subTest(target=target),tempfile.TemporaryDirectory() as d:
                p=Path(d);model,raw,snapshot=self.fixture(p)
                (model if target=='model' else snapshot).write_text('changed')
                with self.assertRaises(ValueError):reuse_snapshot(p,[model],raw,['n'])
    def test_incomplete_reference_or_boundary_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);model,raw,_=self.fixture(p)
            with self.assertRaises(ValueError):reuse_snapshot(p,[model],raw,['other'])
            (p/'status.json').write_text(json.dumps(dict(state='conditional_detector_native_running')))
            with self.assertRaises(ValueError):reuse_snapshot(p,[model],raw,['n'])

if __name__=='__main__':unittest.main()
