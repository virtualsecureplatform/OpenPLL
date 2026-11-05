"""Campaign preparation binds geometry and never promotes it to qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from common_v2 import ROOT,PROFILE,save,sha,source_pins
from prepare_candidate_v3 import prepare

class CurrentCandidatePreparation(unittest.TestCase):
    def fixture(self,root):
        layout=root/'layout';layout.mkdir();gds=layout/'assembly.gds';gds.write_bytes(b'fixture only')
        pins=source_pins();pins.pop(str(PROFILE));pins[str(ROOT/'verification/prototype_400mhz.json')]=sha(ROOT/'verification/prototype_400mhz.json')
        checked=dict(input_sha256=pins,artifacts={str(gds):sha(gds)},
            assembled_drc_pass=True,assembled_lvs_pass=True,all_three_macros_expanded=True,
            all_source_macro_geometry_and_labels_preserved=True)
        save(layout/'assessment.json',checked)
        closure=root/'closure';closure.mkdir();(closure/'layout').symlink_to(layout,target_is_directory=True)
        receipt=dict(input_sha256={str(layout/'assessment.json'):sha(layout/'assessment.json')},artifacts={},
            filled_geometry_checks_pass=True,assembled_drc_pass=True,assembled_lvs_pass=True,
            complete_port_connectivity_screen_passed=True,stock_density_checks_passed=True,
            forming_antenna_violations=0,native_antenna_feedback=0)
        save(closure/'assessment.json',receipt)
        return closure,layout,checked,receipt

    def test_matching_geometry_still_leaves_all_qualification_gates_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);closure,layout,_,_=self.fixture(root)
            manifest=prepare(closure,root/'campaign')
            self.assertEqual(manifest['candidate']['physical_sha256'],{str(layout/'assembly.gds'):sha(layout/'assembly.gds')})
            status=json.loads((root/'campaign/status.json').read_text())
            self.assertFalse(status['release_qualified'])
            self.assertTrue(all(not row['passed'] for row in status['gates'].values()))
            self.assertEqual(len(json.loads((root/'campaign/functional_matrix.json').read_text())['cases']),180)

    def test_wrong_source_nonpass_density_and_changed_gds_rejected(self):
        for fault in ('source','density','gds','profile'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);closure,layout,checked,receipt=self.fixture(root)
                if fault=='source':
                    checked['input_sha256'].pop(str(ROOT/'rtl/IntegerPLL_ProgrammedCore.v'))
                    save(layout/'assessment.json',checked)
                    receipt['input_sha256'][str(layout/'assessment.json')]=sha(layout/'assessment.json')
                elif fault=='profile':
                    checked['input_sha256'].pop(str(ROOT/'verification/prototype_400mhz.json'))
                    save(layout/'assessment.json',checked)
                    receipt['input_sha256'][str(layout/'assessment.json')]=sha(layout/'assessment.json')
                elif fault=='density':receipt['stock_density_checks_passed']=False
                else:(layout/'assembly.gds').write_bytes(b'changed')
                save(closure/'assessment.json',receipt)
                with self.assertRaises(ValueError):prepare(closure,root/'rejected')
