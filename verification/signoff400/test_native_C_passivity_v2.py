"""Passive signed energy, genuine negative bridge and uncoupled zero controls."""
import unittest
from fractions import Fraction as F
from native_C_passivity_v2 import assess_caps
class Controls(unittest.TestCase):
    def test_signed_passive_triangle(self):
        self.assertTrue(assess_caps([('a','g',F(1)),('b','g',F(1)),('a','b',F(-1,10))])['linear_C_PSD_certified'])
    def test_negative_bridge(self):
        self.assertFalse(assess_caps([('a','g',F(1)),('a','b',F(-1,10**40))])['linear_C_PSD_certified'])
    def test_negative_overwhelms_support(self):
        self.assertFalse(assess_caps([('a','g',F(1)),('b','g',F(1)),('a','b',F(-1))])['linear_C_PSD_certified'])
    def test_zero_and_positive(self):
        self.assertTrue(assess_caps([('a','b',F(0)),('b','g',F(1))])['linear_C_PSD_certified'])
if __name__=='__main__':unittest.main()
