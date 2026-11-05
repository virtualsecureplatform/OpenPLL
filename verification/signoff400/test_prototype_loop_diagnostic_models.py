from fractions import Fraction as F
import unittest
from prepare_prototype_loop_diagnostic import interpolate_period


class DiagnosticInterpolation(unittest.TestCase):
    def test_native_endpoints_retained_and_no_extrapolation(self):
        a=dict(corner='sf',coarse_code=1,fine_code=8,average_frequency_hz=380000000)
        b=dict(corner='sf',coarse_code=1,fine_code=248,average_frequency_hz=480000000)
        with self.assertRaises(ValueError):interpolate_period(a,b)
        b['fine_code']=247;table=interpolate_period(a,b)
        self.assertEqual(table[8],F(380000000))
        self.assertEqual(table[247],F(480000000))
        self.assertNotIn(7,table);self.assertNotIn(248,table)
        self.assertTrue(all(table[i]<table[i+1] for i in range(8,247)))
        b['corner']='ss'
        with self.assertRaises(ValueError):interpolate_period(a,b)

    def test_decreasing_fine_response_supported(self):
        a=dict(corner='ff',coarse_code=5,fine_code=8,average_frequency_hz=450000000)
        b=dict(corner='ff',coarse_code=5,fine_code=247,average_frequency_hz=350000000)
        table=interpolate_period(a,b)
        self.assertTrue(all(table[i]>table[i+1] for i in range(8,247)))


if __name__=='__main__':unittest.main()
