import unittest
from prototype_native_literal_templates import review
from prototype_native_literal_templates_v2 import factor


class LiteralTemplatesWithC(unittest.TestCase):
    source = ('* source with explicit signed C and numerical guard\n'
              '.subckt Top A B\n'
              'Cflat0 A B -1e-15\n'
              'Xflat0 A B 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15\n'
              'Ckron0 A 0 2e-15\n'
              'RparentWire0 A B 3\n'
              'Cguard0 B 0 1e-20\n.ends Top\n')

    def test_preserves_all_signed_capacitor_cards_and_order(self):
        text, counts = factor(self.source)
        self.assertEqual(counts['explicit_capacitor_cards_preserved'], 3)
        self.assertEqual([s for s in text.splitlines() if s.startswith('C')],
                         [s for s in self.source.splitlines() if s.startswith('C')])
        self.assertTrue(review(self.source, text))
        for wrong in (text.replace('-1e-15', '1e-15'), text.replace('Cguard0 B', 'Cguard0 A')):
            with self.assertRaises(ValueError):
                review(self.source, wrong)

    def test_rejects_expressions_nonfinite_values_and_duplicate_C(self):
        for wrong in (self.source.replace('-1e-15', '{k}'),
                      self.source.replace('-1e-15', 'nan'),
                      self.source.replace('Cguard0', 'cFLAT0')):
            with self.assertRaises(ValueError):
                factor(wrong)


if __name__ == '__main__':
    unittest.main()
