from pathlib import Path
import sys
import unittest
from recover_prototype_DCO_duplicate_rows import parse
from assess_prototype_native_waveform import crossings
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from spice_dco_postlayout_prototype_v6 import ngspice_printed_waveform


class DuplicateRowsTests(unittest.TestCase):
    def text(self):
        return ('No. of Data Rows : 5\n0 0 0\n1 1e-9 1.8\n2 1e-9 1.8\n'
                '3 2e-9 0\n4 3e-9 1.8\nTotal analysis time (seconds) = 1\n')

    def test_exact_duplicate_recovery_preserves_all_interpolated_crossings(self):
        points,duplicates,count=parse(self.text())
        raw=[(0,0),(1e-9,1.8),(1e-9,1.8),(2e-9,0),(3e-9,1.8)]
        self.assertEqual(crossings(points,.9),crossings(raw,.9))
        self.assertEqual((len(points),len(duplicates),count),(4,1,5))
        self.assertEqual(ngspice_printed_waveform(self.text()),points)

    def test_time_collision_with_changed_voltage_is_not_discarded(self):
        text=self.text().replace('2 1e-9 1.8','2 1e-9 1.7')
        for parser in (parse,ngspice_printed_waveform):
            with self.assertRaises(ValueError):parser(text)

    def test_decreasing_time_is_not_a_duplicate(self):
        text=self.text().replace('2 1e-9 1.8','2 .9e-9 1.8')
        for parser in (parse,ngspice_printed_waveform):
            with self.assertRaises(ValueError):parser(text)

    def test_missing_native_rows_rejected(self):
        text=self.text().replace('2 1e-9 1.8\n','')
        for parser in (parse,ngspice_printed_waveform):
            with self.assertRaises(ValueError):parser(text)


if __name__=='__main__':unittest.main()
