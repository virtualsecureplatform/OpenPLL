import unittest
from export_selected_conditional_bench import retain_card

class PartitionTests(unittest.TestCase):
    def test_private_to_boundary_coupling_retained(self):self.assertTrue(retain_card('C1 private boundary 1e-15',set(),{'private'}))
    def test_boundary_only_cap_is_not_in_private_kcl(self):self.assertFalse(retain_card('C1 boundary outside 1e-15',set(),{'private'}))
    def test_all_wire_resistors_preserved(self):self.assertTrue(retain_card('R1 a b 42',set(),set()))
    def test_selected_device_preserved(self):self.assertTrue(retain_card('Xflat1 a b leaf',{'xflat1'},set()))
    def test_exterior_device_excluded(self):self.assertFalse(retain_card('Xflat2 a b leaf',{'xflat1'},set()))
    def test_unknown_card_cannot_be_silently_dropped(self):
        with self.assertRaises(ValueError):retain_card('B1 a b V=1',set(),set())

if __name__=='__main__':unittest.main()
