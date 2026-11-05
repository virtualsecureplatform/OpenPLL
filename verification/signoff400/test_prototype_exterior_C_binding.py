import unittest
from bind_prototype_exterior_capacitance_nodes import bindings


class ExteriorBinding(unittest.TestCase):
    def test_canonical_aliases_share_one_attachment_without_grounding_remote_nodes(self):
        rows=[dict(pin='A',node='outside'),dict(pin='cell/A',node='outside')]
        bound,mapping=bindings(rows,'Top',{'A':'wire7','Top/cell/A':'wire7'},{'wire7'})
        self.assertEqual(mapping,{'outside':'wire7'})
        self.assertEqual(len(bound),2)

    def test_missing_conflicting_and_eliminated_points_rejected(self):
        rows=[dict(pin='A',node='outside'),dict(pin='B',node='outside')]
        for voltage,live in [({'A':'x'},{'x'}),({'A':'x','B':'y'},{'x','y'}),({'A':'x','B':'x'},{'y'})]:
            with self.subTest(voltage=voltage),self.assertRaises(ValueError):bindings(rows,'Top',voltage,live)


if __name__=='__main__':unittest.main()
