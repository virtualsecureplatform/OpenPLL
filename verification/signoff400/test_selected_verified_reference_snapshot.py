import contextlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common_v3 import save, sha
from resources import identity
from capture_selected_verified_reference_snapshot import run


class VerifiedReferenceSnapshotTest(unittest.TestCase):
    def fixture(self, root):
        native = root/'native'; native.mkdir()
        reference = root/'reference'; reference.mkdir()
        manifest = native/'manifest.json'
        save(manifest, dict(input_sha256={}))
        save(native/'status.json', dict(state='native_startup_completed_waveform_assessment_pending'))
        save(native/'native.process.json', dict(pid=2147483647, birth='missing'))
        raw = native/'profile.raw'
        raw.write_text('No. Variables: 2\nVariables:\n0 time time\n1 v(test) voltage\nValues:\n0 0\n1.8\n')
        assessment = reference/'assessment.json'
        save(assessment, dict(end_ns=260, samples=3))
        provenance = reference/'provenance.json'
        save(provenance, dict(input_sha256={str(manifest): sha(manifest)},
             artifacts={str(assessment): sha(assessment)}, native_input_sha256={}, raw_sha256=sha(raw)))
        return native, provenance

    def call(self, native, provenance, output):
        with patch('capture_selected_verified_reference_snapshot.os.sched_setaffinity'), \
             patch('capture_selected_verified_reference_snapshot.lease', return_value=contextlib.nullcontext()):
            run(native, provenance, output)

    def test_fixture_snapshot_preserves_initial_vector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); native, provenance = self.fixture(root)
            self.call(native, provenance, root/'out')
            result = json.loads((root/'out/initial_voltage_vector.json').read_text())
            self.assertEqual(result['values'], [0.0, 1.8])
            self.assertFalse(json.loads((root/'out/assessment.json').read_text())['release_ready'])

    def test_changed_raw_and_live_native_rejected(self):
        for damage in ('raw', 'live', 'manifest'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); native, provenance = self.fixture(root)
                if damage == 'raw':
                    with (native/'profile.raw').open('a') as stream: stream.write('tampered\n')
                elif damage == 'live':
                    save(native/'native.process.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
                else:
                    save(native/'manifest.json', dict(input_sha256={}, altered=True))
                with self.assertRaises(ValueError): self.call(native, provenance, root/'out')
                self.assertFalse((root/'out/assessment.json').exists())
                self.assertEqual(json.loads((root/'out/status.json').read_text())['state'], 'stopped_without_qualification')


if __name__ == '__main__':
    unittest.main()
