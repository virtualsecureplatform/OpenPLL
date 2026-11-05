import unittest
from spice_dco_postlayout_prototype_v3 import ngspice_printed_waveform


class PrintedWaveformControls(unittest.TestCase):
    def test_page_headers_and_high_precision_values(self):
        text = '''Index time v(pllout)
0 0.000000000000000e+00 9.000000000000000e-01
1 1.000000000000000e-12 9.010000000000001e-01
Index time v(pllout)
2 2.000000000000000e-12 9.020000000000002e-01
freq_hz = 4.0e8
'''
        points = ngspice_printed_waveform(text)
        self.assertEqual(len(points), 3)
        self.assertEqual(points[2], (2e-12, 0.9020000000000002))

    def test_missing_rows_duplicates_nonmonotonic_and_absent_trace_rejected(self):
        for text in ('', '0 0 0\n2 1e-12 1\n', '0 0 0\n0 1e-12 1\n',
                     '0 0 0\n1 0 1\n', '0 0 0\n1 -1e-12 1\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                ngspice_printed_waveform(text)


if __name__ == '__main__':
    unittest.main()
