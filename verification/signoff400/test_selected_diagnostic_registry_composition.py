"""Check registry composition preserves native data and rejects corner leakage."""
import json
from pathlib import Path
import tempfile
import unittest
from common_v3 import ROOT
from compose_selected_diagnostic_registry import compose


class RegistryCompositionControls(unittest.TestCase):
    def test_actual_composition_reproduces_control_registry(self):
        base = ROOT/'build/signoff400'
        with tempfile.TemporaryDirectory() as temp:
            result = compose(base/'selected_target_calibration_pipeline_316/selected_interface/models.json',
                base/'selected_root_publication_detector_407',Path(temp)/'models.json')
            expected = json.loads((base/'selected_TT_stress_registry_945/models.json').read_text())
            self.assertEqual(result,expected)
            original = json.loads((base/'selected_target_calibration_pipeline_316/selected_interface/models.json').read_text())
            self.assertEqual(result['points'],original['points'])
            self.assertEqual(result['analog'],original['analog'])

    def test_mismatched_corner_composition_rejected(self):
        base = ROOT/'build/signoff400'
        data = json.loads((base/'selected_root_publication_detector_407/assessment.json').read_text())
        data['operating_point']['corner'] = 'ss'
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'composition';folder.mkdir()
            (folder/'assessment.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'operating points differ'):
                compose(base/'selected_target_calibration_pipeline_316/selected_interface/models.json',
                    folder,Path(temp)/'models.json')


if __name__ == '__main__':
    unittest.main()
