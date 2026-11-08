import json
import tempfile
import unittest
from pathlib import Path
from audit_magic_coupling_relocation import audit


class RelocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'trace'
        b = dict(cell='top', epoch=1)
        self.rows = [dict(b, kind='overlap', node1_id='A', node2_id='S', cap_native_hex=0.1.hex()),
                     dict(b, kind='ground_update', node_id='A', site='relocate', has_before=True,
                          before_hex=0.2.hex(), after_hex=(0.2 + 0.1).hex()),
                     dict(b, kind='ground_output', node_id='A', name='A', substrate=False),
                     dict(b, kind='ground_output', node_id='S', name='GND', substrate=True)]

    def run_audit(self):
        self.path.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        return audit(self.path, {'relocate'})

    def test_native_rounded_addition_proves_relocation(self):
        r = self.run_audit()
        self.assertTrue(r['all_nonexported_pairs_classified'])
        self.assertEqual(r['native_substrate_relocation_additions_verified'], 1)

    def test_missing_relocation_update_is_rejected(self):
        self.rows.pop(1)
        with self.assertRaisesRegex(ValueError, 'missing native'):
            self.run_audit()

    def test_names_alone_do_not_prove_export(self):
        b = dict(cell='top', epoch=1)
        self.rows += [dict(b, kind='sidewall', node1_id='A', node2_id='B', cap_native_hex=1.0.hex()),
                      dict(b, kind='ground_output', node_id='B', name='B', substrate=False)]
        r = self.run_audit()
        self.assertFalse(r['all_nonexported_pairs_classified'])
        self.assertEqual(r['pair_classes']['unresolved'], 1)


if __name__ == '__main__':
    unittest.main()
