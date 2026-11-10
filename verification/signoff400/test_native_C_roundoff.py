"""Reject missing small capacitors and wrong totals; admit float64 serialization residue."""
import unittest
from native_C_roundoff import assess
class Controls(unittest.TestCase):
    def test_small_cap_not_erased(self):
        self.assertFalse(assess('C0 a b 2.5e-19','C0 a b 0')['float64_C_conservation'])
    def test_distributed_roundoff(self):
        r=assess('C0 a 0 1e-15','R0 a x 1\nC0 a 0 3.0000000000000004e-16\nC1 x 0 7e-16')
        self.assertTrue(r['native_devices_and_C_conserved']);self.assertFalse(r['exact_cap_contraction'])
    def test_duplicate_ground_rejected(self):
        self.assertFalse(assess('C0 a 0 1e-15','R0 a x 1\nC0 a 0 1e-15\nC1 x 0 1e-15')['float64_C_conservation'])
    def test_new_pair_rejected(self):
        self.assertFalse(assess('C0 a b 0','C0 a b 1e-40')['float64_C_conservation'])
if __name__=='__main__':unittest.main()
