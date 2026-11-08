import unittest
from fractions import Fraction as F
from audit_keeper_DCO_driver_C_cut import capacitance

class CapacitanceUnits(unittest.TestCase):
    def test_native_suffixes_preserve_exact_value(self):
        self.assertEqual(capacitance('11.1247p'), F('11.1247')/10**12)
        self.assertEqual(capacitance('0.08811f'), F('0.08811')/10**15)
    def test_zero_and_scientific_notation(self):
        self.assertEqual(capacitance('0'),0)
        self.assertEqual(capacitance('2e-15'),capacitance('2f'))
    def test_unknown_suffix_rejected(self):
        with self.assertRaises(ValueError):capacitance('2q')

if __name__=='__main__':unittest.main()
