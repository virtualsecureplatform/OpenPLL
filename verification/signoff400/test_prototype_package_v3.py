import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from package_prototype_v3 import ROLES, add_pins, destination, run
from common_v3 import sha


class PrototypePackageTests(unittest.TestCase):
    def test_portable_destination(self):
        self.assertEqual(destination('models/dco/nom.spice'), 'models/dco/nom.spice')
        for value in ('/tmp/model.spice', '../model.spice', 'models/../model.spice',
                      'models//model.spice', '', '.', 'assessment.json',
                      'assessment.json/child', 'models\\model.spice'):
            with self.assertRaises(ValueError):
                destination(value)

    def test_conflicting_receipts_rejected(self):
        pins = {'model': 'first'}
        add_pins(pins, {'model': 'first'})
        with self.assertRaises(ValueError):
            add_pins(pins, {'model': 'second'})

    def test_staging_preserves_bytes_without_claiming_replay(self):
        # Isolate the copy/provenance boundary; real qualification is exercised
        # by the campaign audit, never fabricated by this package test.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source.v'
            source.write_bytes(b'qualified source bytes\x00\n')
            pins = {str(source): sha(source)}
            evidence = root/'evidence.json'
            evidence.write_text(json.dumps(dict(input_sha256=pins, artifacts=pins)))
            gates = ('physical_integrity', 'analog_models_and_tuning',
                     'digital_timing_and_cdc', 'closed_loop_operation', 'reproducible_handoff')
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps(dict(
                candidate=dict(source_sha256=pins, physical_sha256=pins),
                evidence={g: [dict(path=str(evidence), sha256=sha(evidence))] for g in gates},
                handoff_artifacts={role: [dict(source=str(source), destination=role+'/file')]
                                   for role in ROLES})))
            report = dict(identity_failures=[], gates={g: dict(status='pass') for g in gates})
            output = root/'package'
            with patch('package_prototype_v3.audit', return_value=report):
                run(manifest, output)
            for role in ROLES:
                self.assertEqual((output/role/'file').read_bytes(), source.read_bytes())
            receipt = json.loads((output/'assessment.json').read_text())
            self.assertTrue(receipt['package_staged'])
            self.assertFalse(receipt['release_ready'])
            self.assertFalse(receipt['portable_paths_verified'])
            self.assertFalse(receipt['clean_environment_replay_complete'])
