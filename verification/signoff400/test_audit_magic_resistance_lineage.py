import json
import tempfile
import unittest
from pathlib import Path
from audit_magic_resistance_lineage import audit


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trace = Path(self.tmp.name) / 'trace'
        self.ext = Path(self.tmp.name) / 'res.ext'
        self.rows = []
        def event(kind, node='A', before=0., source=0., after=0., scale=0., **extra):
            return dict(kind=kind, node_id=node, before_hex=float(before).hex(),
                        source_hex=float(source).hex(), after_hex=float(after).hex(),
                        scale_hex=float(scale).hex(), placement_qualified=False, **extra)
        self.rows = [event('res_node_init'), event('res_node_init', 'B'),
                     event('raw_resistance_area', after=1., native_added_hex=1.0.hex()),
                     event('raw_resistance_area', 'B', after=2., native_added_hex=2.0.hex()),
                     event('res_node_merge', before=1., source=2., after=3., other_id='B'),
                     event('res_distribution_input', after=3.),
                     event('res_distribution_scale', before=3., source=6., after=2.),
                     event('res_distribution_output', before=3., after=6., scale=2.),
                     event('res_node_output', source=1., after=6., scale=6., name='A.n0')]
        self.ext.write_text('rnode "A.n0" 0 1 0 0 0\n')

    def run_audit(self):
        self.trace.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        return audit(self.trace, self.ext)

    def test_merge_and_distribution_reconstruct_export(self):
        r = self.run_audit()
        self.assertTrue(r['exported_rnode_records_match'])
        self.assertEqual(r['observed_merges'], 1)
        self.assertFalse(r['capacitance_placement_qualified'])

    def test_missing_merge_is_rejected(self):
        self.rows.pop(4)
        with self.assertRaisesRegex(ValueError, 'continuity'):
            self.run_audit()

    def test_missing_initialization_is_rejected(self):
        self.rows.pop(1)
        with self.assertRaisesRegex(ValueError, 'continuity'):
            self.run_audit()

    def test_wrong_distribution_is_rejected(self):
        self.rows[7]['after_hex'] = 7.0.hex()
        with self.assertRaisesRegex(ValueError, 'scaling'):
            self.run_audit()

    def test_export_mismatch_stays_visible(self):
        self.ext.write_text('rnode "A.n0" 0 2 0 0 0\n')
        self.assertFalse(self.run_audit()['exported_rnode_records_match'])


if __name__ == '__main__':
    unittest.main()
