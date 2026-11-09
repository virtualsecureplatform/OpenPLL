import unittest
from compare_native_R_with_aliases import compare_with_aliases

class AliasContraction(unittest.TestCase):
    base='.subckt top a afar b\nRalias a afar 0\nC1 a b 1f\n.ends\n'
    candidate='.subckt top a afar b\nR1 a mid 1\nR2 mid afar 2\nC1 mid b 1f\n.ends\n'
    def test_real_wire_with_explicit_reference_alias_passes(self):
        r=compare_with_aliases(self.base,self.candidate)
        self.assertTrue(r['exact_device_and_C_contraction_verified']);self.assertEqual(r['positive_wire_R_cards'],2)
    def test_capacitance_duplication_is_not_hidden(self):
        r=compare_with_aliases(self.base,self.candidate.replace('1f','2f'))
        self.assertFalse(r['exact_device_and_C_contraction_verified'])
    def test_new_shorts_and_interface_changes_rejected(self):
        r=compare_with_aliases(self.base,self.candidate.replace('R2 mid afar 2','R2 mid b 2'))
        self.assertFalse(r['exact_device_and_C_contraction_verified'])
        with self.assertRaises(ValueError):compare_with_aliases(self.base,self.candidate.replace('top a afar b','top afar a b'))
        with self.assertRaises(ValueError):compare_with_aliases(self.base.replace('afar 0','afar 1'),self.candidate)

if __name__=='__main__':unittest.main()
