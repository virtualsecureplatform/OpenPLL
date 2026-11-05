import unittest
from prototype_native_literal_templates import factor, review


class LiteralTemplates(unittest.TestCase):
    source = ('.subckt Top A B\n'
              'Xflat0 A n B B sky130_fd_pr__nfet_01v8 w=1 l=0.15\n'
              'Xflat1 n B B B sky130_fd_pr__nfet_01v8 w=1 l=0.15\n'
              'Xflat2 B A n B sky130_fd_pr__nfet_01v8 w=2 l=0.15\n'
              'RparentWire0 n B 2\n.ends Top\n')

    def test_shares_only_identical_literals_and_recovers_all_cards(self):
        text, counts = factor(self.source)
        self.assertEqual(counts, dict(primitives=3, literal_templates=2))
        self.assertTrue(review(self.source, text))
        self.assertIn('RparentWire0 n B 2', text)

    def test_actual_file_review_rejects_terminal_parameter_resistor_changes(self):
        text, _ = factor(self.source)
        for wrong in (text.replace('Xflat1 n B B B', 'Xflat1 B n B B'),
                      text.replace('w=1 ', 'w=3 '),
                      text.replace('n B 2', 'n B 3'),
                      text.replace('Xdevice p0 p1 p2 p3', 'Xdevice p1 p0 p2 p3')):
            with self.assertRaises(ValueError):
                review(self.source, wrong)

    def test_rejects_scoped_values_directives_duplicates_and_reserved_names(self):
        for wrong in (self.source.replace('w=1', 'w={k}'),
                      self.source.replace('w=1', 'w=nan'),
                      self.source.replace('RparentWire0 n B 2', '.param k=1'),
                      self.source.replace('Xflat1', 'Xflat0'),
                      self.source.replace('Top A B', 'Top A B m=1'),
                      self.source.replace('Top A B', 'Top A __openpll_literal_leaf_0')):
            with self.assertRaises(ValueError):
                factor(wrong)


if __name__ == '__main__':
    unittest.main()
