from fractions import Fraction as F
import unittest
from native_spice_comments import strip_floating_annotation
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance_v2 import flatten as aggregate
from prototype_capacitance_aliases_v2 import flatten as aliases


class NativeFloatingAnnotations(unittest.TestCase):
    def test_floating_signed_capacitors_remain_in_both_operators(self):
        text='.subckt top A VGND\nC0 A floating 2f $ **FLOATING\nC1 floating VGND -1f $ **FLOATING\nR0 alias A 0\nC2 alias VGND 3f\n.ends top\n'
        a,counts=aggregate(subcircuits(text),'top');b,other,resolve=aliases(subcircuits(text),'top')
        self.assertEqual(a,b);self.assertEqual(counts['expanded_capacitors'],3)
        self.assertEqual(other['expanded_capacitors'],3)
        self.assertTrue(any('top/floating' in pair for pair in a))
        self.assertIn(-F(1,10**15),a.values());self.assertEqual(resolve('A'),resolve('top/alias'))

    def test_dollar_identifiers_are_preserved(self):
        line='C0 node$abc$ other$ 1f $ **FLOATING'
        self.assertEqual(strip_floating_annotation(line),'C0 node$abc$ other$ 1f')
        self.assertEqual(strip_floating_annotation('C0 node$abc$ other$ 1f'),'C0 node$abc$ other$ 1f')

    def test_unknown_annotations_and_extra_electrical_tokens_rejected(self):
        for suffix in ('$ **UNKNOWN','**FLOATING',' $ **FLOATING extra','2f'):
            text='.subckt top A B\nC0 A B 1f '+suffix+'\n.ends top\n'
            for parser in (aggregate,aliases):
                with self.assertRaises(ValueError):parser(subcircuits(text),'top')


if __name__=='__main__':unittest.main()
