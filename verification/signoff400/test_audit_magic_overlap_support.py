import json
import tempfile
import unittest
from pathlib import Path
from audit_magic_overlap_support import reconstruct, subtract, area


class ShieldingSupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trace = Path(self.tmp.name) / 'trace'
        base = dict(cell='top', epoch=1, overlap_id=1, node1_id='A', node2_id='B',
                    box=[0, 0, 40, 10], native_area=400, plane1=1, plane2=3,
                    coefficient_hex=1.0.hex(), split=False,
                    pointwise_placement_qualified=False)
        self.rows = [dict(base, kind='overlap_support_begin'),
                     dict(base, kind='overlap_shield_leaf', box=[0, 0, 20, 10], native_area=200),
                     dict(base, kind='overlap_support_end', native_area=200)]

    def run_audit(self):
        self.trace.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        emitted = []
        result = reconstruct(self.trace, emitted.append)
        return result, emitted

    def test_half_shield_preserves_surviving_location(self):
        r, emitted = self.run_audit()
        self.assertTrue(r['all_overlap_support_reconstructed'])
        self.assertEqual(emitted[0]['rectangles'], [[20, 0, 40, 10]])

    def test_interior_hole_preserves_disjoint_pieces(self):
        parts = subtract([0, 0, 40, 10], [10, 2, 30, 8])
        self.assertEqual(len(parts), 4)
        self.assertEqual(sum(map(area, parts)), 280)
        # Removing the same region again must leave all pieces unchanged.
        self.assertEqual(parts, [p for old in parts for p in subtract(old, [10, 2, 30, 8])])

    def test_duplicate_shield_is_rejected(self):
        self.rows.insert(2, dict(self.rows[1]))
        self.rows[-1]['native_area'] = 0
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            self.run_audit()

    def test_truncated_overlap_is_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError, 'complete extraction'):
            self.run_audit()

    def test_split_leaf_never_claims_rectangular_support(self):
        self.rows[1]['split'] = True
        r, emitted = self.run_audit()
        self.assertFalse(r['all_overlap_support_reconstructed'])
        self.assertEqual(r['unsupported_split_cases'], 1)
        self.assertIsNone(emitted[0]['rectangles'])


if __name__ == '__main__':
    unittest.main()
