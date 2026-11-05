import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from run_selected_streaming_control_v2 import prerequisite


class ExtendedPrerequisiteTests(unittest.TestCase):
    def test_rejects_incomplete_or_changed_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);reference=root/'reference.csv';reference.write_text('native')
            prior=root/'prior.json'
            value=dict(within_diagnostic_voltage_tolerance=True,end_s=21e-9,channels=31,
                DC_comparison=False,input_sha256={str(reference):sha(reference)})
            prior.write_text(json.dumps(value));self.assertEqual(prerequisite(prior,reference)['channels'],31)
            value['within_diagnostic_voltage_tolerance']=False;prior.write_text(json.dumps(value))
            self.assertFalse(prerequisite(prior,reference)['within_diagnostic_voltage_tolerance'])
            value['channels']=6;prior.write_text(json.dumps(value))
            with self.assertRaises(ValueError):prerequisite(prior,reference)
            value['channels']=31;prior.write_text(json.dumps(value));reference.write_text('changed')
            with self.assertRaises(ValueError):prerequisite(prior,reference)


if __name__=='__main__':unittest.main()
