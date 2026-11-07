import unittest
from fractions import Fraction as F
from audit_local_C_principal_energy import witness
from project_prototype_fixed_rail_C_v2 import FIXED

class PrincipalEnergy(unittest.TestCase):
    def test_negative_diagonal(self):
        result=witness({('a',FIXED):F(-1)})
        self.assertTrue(result['indefiniteness_proved'])
        self.assertEqual(F(result['exact_twice_energy_J']),-1)
    def test_positive_diagonals_indefinite_pair(self):
        result=witness({('a','b'):F(-2),('a',FIXED):F(3),('b',FIXED):F(3)})
        self.assertTrue(result['indefiniteness_proved'])
        self.assertEqual(F(result['exact_twice_energy_J']),-3)
    def test_passive_network_not_rejected(self):
        self.assertFalse(witness({('a','b'):F(2),('a',FIXED):F(3)})['indefiniteness_proved'])
    def test_no_certificate_does_not_claim_psd(self):
        result=witness({('a','b'):F(-2),('b','c'):F(-2),('a','c'):F(-2),('a',FIXED):F(8),('b',FIXED):F(8),('c',FIXED):F(8)})
        self.assertFalse(result['indefiniteness_proved'])
        self.assertIn('no PSD certificate',result['scope'])

if __name__=='__main__':unittest.main()
