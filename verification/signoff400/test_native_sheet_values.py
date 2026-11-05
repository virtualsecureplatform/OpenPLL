from fractions import Fraction
import unittest
from check_native_sheet_values import expected, check_row


class NativeSheetValues(unittest.TestCase):
    def row(self):
        return dict(raw_material='psubdiff', flow_axis=1, tile_box_internal=[0, 0, 34, 100],
                    segments=[[0, 83, 'a', 'b', '480911.75', 'p']])

    def test_native_rounding_is_distinct_from_final_double_rounding(self):
        self.assertEqual(expected(Fraction(197000), 83, 34), 480911.75)
        self.assertNotEqual(float(Fraction(197000*83, 34)), 480911.75)
        counts, failures = check_row(self.row(), {'psubdiff': Fraction(197000)})
        self.assertEqual(counts['binary32_exact_matches'], 1)
        self.assertEqual(failures, [])

    def test_one_native_float_step_mutation_is_reported(self):
        r = self.row()
        r['segments'][0][4] = '480911.78125'
        counts, failures = check_row(r, {'psubdiff': Fraction(197000)})
        self.assertEqual(counts['binary32_mismatches'], 1)
        self.assertEqual(len(failures), 1)

    def test_unknown_material_and_bad_geometry_remain_accounted(self):
        counts, failures = check_row(self.row(), {})
        self.assertEqual(counts['native_segments'], counts['segments_without_documented_sheet'])
        r = self.row()
        r['segments'][0][1] = 0
        counts, failures = check_row(r, {'psubdiff': Fraction(197000)})
        self.assertEqual(counts['segments_with_unsupported_geometry'], 1)
        self.assertFalse(failures)
        with self.assertRaises(ValueError):
            expected(Fraction(1), 1, 0)
