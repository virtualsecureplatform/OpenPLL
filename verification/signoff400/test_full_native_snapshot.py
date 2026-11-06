import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from common_v3 import save, sha
from capture_selected_full_native_snapshot import validate


class FullNativeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = self.root / 'native'; self.native.mkdir()
        self.assessment = self.root / 'assessment'; self.assessment.mkdir()
        save(self.native / 'status.json', dict(state='native_startup_completed_waveform_assessment_pending'))
        deck = self.native / 'profile.spice'
        deck.write_text('.lib models.spice ss\n.options device temp=27\n')
        self.inputs = {str(deck): sha(deck)}
        save(self.native / 'manifest.json', dict(input_sha256=self.inputs))
        save(self.assessment / 'assessment.json', dict(samples=3, end_ns=260))
        self.provenance = dict(
            input_sha256={str(self.native / 'manifest.json'): sha(self.native / 'manifest.json')},
            native_input_sha256=self.inputs.copy(), raw_sha256='a' * 64,
            artifacts={str(self.assessment / 'assessment.json'): sha(self.assessment / 'assessment.json')})
        self.write()

    def write(self):
        save(self.assessment / 'provenance.json', self.provenance)

    def test_actual_corner(self):
        digest, conditions = validate(self.native, self.assessment)
        self.assertEqual(digest, 'a' * 64)
        self.assertEqual(conditions, dict(corner='ss', temperature_c=27))

    def test_live_run_rejected(self):
        save(self.native / 'status.json', dict(state='running_loaded_startup_260ns'))
        with self.assertRaisesRegex(ValueError, 'normally completed'):
            validate(self.native, self.assessment)

    def test_foreign_manifest_rejected(self):
        self.provenance['input_sha256'][str(self.native / 'manifest.json')] = 'b' * 64
        self.write()
        with self.assertRaisesRegex(ValueError, 'different native'):
            validate(self.native, self.assessment)

    def test_incomplete_horizon_rejected_even_with_matching_checksum(self):
        p = self.assessment / 'assessment.json'
        save(p, dict(samples=3, end_ns=259))
        self.provenance['artifacts'][str(p)] = sha(p); self.write()
        with self.assertRaisesRegex(ValueError, '260 ns'):
            validate(self.native, self.assessment)

    def test_changed_deck_rejected(self):
        (self.native / 'profile.spice').write_text('.lib models.spice tt\n.options device temp=27\n')
        with self.assertRaisesRegex(ValueError, 'deck identity'):
            validate(self.native, self.assessment)

    def test_changed_assessment_rejected(self):
        save(self.assessment / 'assessment.json', dict(samples=4, end_ns=260))
        with self.assertRaisesRegex(ValueError, 'artifact identity'):
            validate(self.native, self.assessment)


if __name__ == '__main__':
    unittest.main()
