import json
import tempfile
import unittest
from pathlib import Path
from audit_magic_coupling_geometry_trace import reconstruct


class NativeRoundingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace = self.root / 'trace.jsonl'
        self.ext = self.root / 'flat.ext'
        self.rows = []
        for node in ['one', 'two']:
            self.rows.append(dict(kind='overlap', cell='top', epoch=1,
                                  node1_id=node, node2_id='other',
                                  cap_native_hex=float(1.234564).hex(),
                                  cap_scale_hex=float(1).hex(),
                                  pointwise_placement_qualified=False))
            self.rows.append(dict(kind='node_name', cell='top', epoch=1,
                                  node_id=node, name='A'))
        self.rows.append(dict(kind='node_name', cell='top', epoch=1,
                              node_id='other', name='B'))

    def audit(self):
        self.trace.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        return reconstruct(self.trace, self.ext)

    def test_native_pairs_round_before_printed_aliases_are_summed(self):
        self.ext.write_text('cap "A" "B" 1.23456\ncap "A" "B" 1.23456\n')
        self.assertTrue(self.audit()['all_exported_C_pairs_reconstructed_at_native_precision'])
        self.ext.write_text('cap "A" "B" 2.46913\n')
        self.assertFalse(self.audit()['all_exported_C_pairs_reconstructed_at_native_precision'])

    def test_unmapped_contributions_remain_visible(self):
        self.rows = [r for r in self.rows if r.get('node_id') != 'other']
        self.ext.write_text('')
        result = self.audit()
        self.assertEqual(result['unmapped_events'], 2)
        self.assertEqual(result['unmapped_pointer_pairs'], 2)
        self.assertFalse(result['ground_capacitance_geometry_traced'])

    def test_repeated_extraction_epoch_is_rejected(self):
        self.rows.append(dict(self.rows[0], epoch=2))
        self.ext.write_text('')
        with self.assertRaisesRegex(ValueError, 'one extraction'):
            self.audit()


if __name__ == '__main__':
    unittest.main()
