import copy
import json
from pathlib import Path
import tempfile
import unittest

from common import PROFILE, cases, sha, source_pins
from run_loop import load_models


class ScopeAndModelChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        table=self.root/'table';table.write_text('1 128 400000000000\n')
        detector=self.root/'detector.v';detector.write_text('// synthetic\n')
        self.value=dict(corner='tt',synthetic=True,profile_sha256=sha(PROFILE),
            candidate_source_sha256=source_pins(),input_sha256={str(p):sha(p) for p in (table,detector)},
            dco_table=str(table),detector_rtl=str(detector),coarse=1,seed=128,polarity=1)

    def load(self,value=None,diagnostic=False):
        path=self.root/'models.json'
        path.write_text(json.dumps(self.value if value is None else value))
        return load_models(path,diagnostic)

    def test_synthetic_requires_explicit_diagnostic(self):
        with self.assertRaisesRegex(ValueError,'synthetic'):self.load()
        self.assertTrue(self.load(diagnostic=True)['synthetic'])

    def test_changed_candidate_cannot_use_old_model(self):
        value=copy.deepcopy(self.value)
        value['candidate_source_sha256'][next(iter(source_pins()))]='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):self.load(value,True)

    def test_profile_and_table_identity_are_required(self):
        value=copy.deepcopy(self.value);value['profile_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'profile'):self.load(value,True)
        Path(self.value['dco_table']).write_text('1 128 450000000000\n')
        with self.assertRaisesRegex(ValueError,'changed'):self.load(diagnostic=True)

    def test_physical_claim_without_candidate_is_rejected(self):
        value=copy.deepcopy(self.value);value['synthetic']=False;value['candidate_physical_sha256']={}
        with self.assertRaisesRegex(ValueError,'physical candidate'):self.load(value)

    def test_unpinned_artifact_and_unsupported_corner_rejected(self):
        value=copy.deepcopy(self.value);value['input_sha256'].pop(value['detector_rtl'])
        with self.assertRaisesRegex(ValueError,'unpinned'):self.load(value,True)
        value=copy.deepcopy(self.value);value['corner']='typical'
        with self.assertRaisesRegex(ValueError,'corner'):self.load(value,True)

    def test_matrix_has_five_corner_groups_and_no_mode_transitions(self):
        matrix=cases()
        self.assertEqual(len(matrix),60)
        self.assertEqual(len({c['id'] for c in matrix}),60)
        self.assertEqual({c['mode_mhz'] for c in matrix},{400})
        self.assertEqual({c['temperature_c'] for c in matrix},{27})
        for corner in ('tt','ff','ss','sf','fs'):
            group=[c for c in matrix if c['corner']==corner]
            self.assertEqual(len(group),12)
            self.assertTrue(all(not c['execution_eligible'] and not c['passed'] for c in group))


if __name__=='__main__':unittest.main()
