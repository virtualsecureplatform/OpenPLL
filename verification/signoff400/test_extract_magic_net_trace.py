import json
import tempfile
import unittest
from pathlib import Path
from extract_magic_net_trace import output_suffix, select


class NetSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trace, self.ext, self.selected = [self.root / n for n in ('trace', 'flat.ext', 'selected')]
        base = dict(cell='top', epoch=1)
        def update(before, after, reset=False):
            return dict(base, kind='ground_update', node_id='0xa', has_before=not reset,
                        before_hex=float(before).hex(), after_hex=float(after).hex())
        def ground(node, name, value, substrate=False):
            return dict(base, kind='ground_output', node_id=node, name=name, substrate=substrate,
                        native_hex=float(value).hex(), scale_hex=1.0.hex(), emitted_hex=float(value).hex())
        self.rows = [update(0, 0, True), update(0, 3),
                     dict(base, kind='overlap', node1_id='0xa', node2_id='0xb', cap_native_hex=2.0.hex(), cap_scale_hex=1.0.hex()),
                     dict(base, kind='sidewall', node1_id='0xa', node2_id='0xs', cap_native_hex=5.0.hex(), cap_scale_hex=1.0.hex()),
                     update(3, 8), ground('0xa', 'A', 8), ground('0xb', 'B', 4), ground('0xs', 'SUB', 0, True),
                     dict(base, kind='node_name', node_id='0xa', name='A'),
                     dict(base, kind='node_name', node_id='0xb', name='B')]
        self.ext.write_text('scale 1000 1 1000\ncap "A" "B" 2\n')

    def suffix(self):
        self.trace.write_text(''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in self.rows))
        return output_suffix(self.trace, 'A', window=8)

    def test_backtracking_and_selected_coupling_accounting(self):
        suffix = self.suffix()
        self.assertEqual(suffix['counts']['ground_output'], 3)
        r = select(self.trace, self.ext, 'A', suffix, self.selected)
        self.assertTrue(r['all_target_exported_C_pairs_reconstructed'])
        self.assertEqual(r['native_pointer_pair_classes'], {'exported_coupling': 1, 'substrate_relocated': 1})
        self.assertEqual(r['selected_events'], 6)
        self.assertFalse(r['pointwise_placement_qualified'])

    def test_name_conflict_rejected(self):
        self.rows[-1]['name'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            self.suffix()

    def test_export_mismatch_rejected(self):
        suffix = self.suffix()
        self.ext.write_text('scale 1000 1 1000\ncap "A" "B" 3\n')
        with self.assertRaisesRegex(ValueError, 'reconstruct'):
            select(self.trace, self.ext, 'A', suffix, self.selected)

    def test_missing_ground_update_rejected(self):
        self.rows.pop(4)
        suffix = self.suffix()
        with self.assertRaisesRegex(ValueError, 'ground output state'):
            select(self.trace, self.ext, 'A', suffix, self.selected)


if __name__ == '__main__':
    unittest.main()
