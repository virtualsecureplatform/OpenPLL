import unittest
from inventory_prototype_capture_clock_ranges import table_maxima


class NativeCaptureClockRanges(unittest.TestCase):
    def test_tightest_native_table_limit_is_retained(self):
        text='cell (ff) {\nrise_constraint (capture) { index_1 ("0, 1"); index_2 ("0.01, 0.24"); }\nfall_constraint (capture) { index_1 ("0, 1"); index_2 ("0.01, 0.20"); }\n}'
        self.assertAlmostEqual(table_maxima(text,{'ff'})['ff'],.20e-9)

    def test_missing_and_invalid_native_axes_rejected(self):
        with self.assertRaises(ValueError):table_maxima('cell (ff) {}',{'missing'})
        with self.assertRaises(ValueError):table_maxima('cell (ff) {}',{'ff'})
        for axis in ('0.24, 0.01','0.01, nan','0.01, inf','-1, 0.24'):
            with self.assertRaises(ValueError):
                table_maxima('cell (ff) { rise_constraint (capture) { index_1 ("0, 1"); index_2 ("'+axis+'"); }}',{'ff'})


if __name__=='__main__':unittest.main()
