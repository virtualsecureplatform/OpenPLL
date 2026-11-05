from fractions import Fraction as F
import unittest
from bounded_C_diagonal_guard_v2 import coefficient


class BinaryGuard(unittest.TestCase):
    def test_decimal_and_native_binary_coefficients_both_enclose_required_guard(self):
        for error in (F(1,3*10**9),F(137,99991*10**8),F(7,13*10**10)):
            text,value=coefficient(error);required=error/10**15
            self.assertEqual(value,F(text))
            self.assertGreaterEqual(value,required)
            self.assertGreaterEqual(F.from_float(float(text)),required)


if __name__=='__main__':unittest.main()
