import json
import tempfile
import unittest
from pathlib import Path
from audit_magic_ground_lifecycle import audit


class GroundLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = self.root / 'trace'
        self.ext = self.root / 'ext'
        base = dict(cell='top', epoch=1, node_id='pointer')
        self.rows = [
            dict(base, kind='ground_update', site='init', has_before=False,
                 before_hex=0.0.hex(), after_hex=0.0.hex()),
            dict(base, kind='ground_update', site='shield', has_before=True,
                 before_hex=0.0.hex(), after_hex=(-0.1).hex()),
            dict(base, kind='ground_output', name='A', substrate=False,
                 native_hex=(-0.1).hex(), scale_hex=1000.0.hex(), emitted_hex=0.0.hex()),
        ]
        self.ext.write_text('node "A" 0 0 0 0 m1\n')

    def run_audit(self):
        self.trace.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        return audit(self.trace, self.ext)

    def test_native_negative_export_clamp(self):
        r = self.run_audit()
        self.assertTrue(r['exported_ground_records_match'])
        self.assertEqual(r['negative_export_clamps'], 1)
        self.assertFalse(r['spatial_ground_placement_qualified'])

    def test_missing_mutation_is_rejected(self):
        self.rows[1]['before_hex'] = 1.0.hex()
        with self.assertRaisesRegex(ValueError, 'continuity'):
            self.run_audit()

    def test_unrecorded_final_value_is_rejected(self):
        self.rows[2]['native_hex'] = (-0.2).hex()
        with self.assertRaisesRegex(ValueError, 'recorded state'):
            self.run_audit()

    def test_export_mismatch_stays_visible(self):
        self.ext.write_text('node "A" 0 1 0 0 m1\n')
        r = self.run_audit()
        self.assertFalse(r['exported_ground_records_match'])
        self.assertEqual(r['missing_exported_records'], 1)
        self.assertEqual(r['extra_reconstructed_records'], 1)


if __name__ == '__main__':
    unittest.main()
