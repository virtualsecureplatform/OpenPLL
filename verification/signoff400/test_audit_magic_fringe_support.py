import json
import math
import tempfile
import unittest
from pathlib import Path
from audit_magic_fringe_support import reconstruct


class FringeSupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trace = Path(self.tmp.name) / 'trace'
        fraction = 0.6366 * math.atan(1)
        base = dict(cell='top', epoch=1, fringe_id=1, node1_id='A', node2_id='B',
                    box=[0, 0, 50, 10], boundary=[0, 0, 0, 10], direction=4,
                    reference_length=10, coupling_multiplier_hex=0.02.hex(),
                    substrate_multiplier_hex=0.02.hex(), coupling_fraction_hex=fraction.hex(),
                    substrate_fraction_hex=fraction.hex(), coupling_shield_hex=0.0.hex(),
                    substrate_shield_hex=0.0.hex(), coefficient_hex=1.0.hex(), split=False,
                    pointwise_placement_qualified=False)
        self.rows = [dict(base, kind='fringe_rule_begin'),
                     dict(base, kind='fringe_shield_leaf', box=[0, 0, 50, 5],
                          coupling_shield_hex=(fraction / 2).hex(), substrate_shield_hex=(fraction / 2).hex()),
                     dict(base, kind='fringe_rule_end', coupling_shield_hex=(fraction / 2).hex(),
                          substrate_shield_hex=(fraction / 2).hex())]

    def run_audit(self):
        self.trace.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        support = []
        return reconstruct(self.trace, support.append), support

    def test_half_edge_shield_preserves_weight_and_position(self):
        r, support = self.run_audit()
        self.assertTrue(r['all_rectilinear_fringe_support_verified'])
        self.assertEqual(support[0]['rectangles'], [[0, 5, 50, 10]])

    def test_wrong_native_shield_fraction_rejected(self):
        self.rows[1]['coupling_shield_hex'] = 0.9.hex()
        with self.assertRaisesRegex(ValueError, 'fraction/integral'):
            self.run_audit()

    def test_incomplete_trace_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError, 'completed fringe'):
            self.run_audit()

    def test_split_support_never_qualified(self):
        self.rows[1]['split'] = True
        r, support = self.run_audit()
        self.assertFalse(r['all_rectilinear_fringe_support_verified'])
        self.assertIsNone(support[0]['rectangles'])


if __name__ == '__main__':
    unittest.main()
