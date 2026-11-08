import unittest
import pya
from audit_keeper_digital_macro_reuse import compare_cells


class MacroGeometry(unittest.TestCase):
    def layout(self, x=0, layer=68, label='PIN'):
        layout = pya.Layout()
        layout.dbu = .001
        cell = layout.create_cell('IntegerPLL_ProgrammedCore')
        index = layout.layer(layer, 20)
        cell.shapes(index).insert(pya.Box(x, 0, x + 100, 100))
        cell.shapes(index).insert(pya.Text(label, pya.Trans()))
        return layout

    def test_identical_geometry_matches(self):
        self.assertTrue(compare_cells(self.layout(), self.layout(), 'IntegerPLL_ProgrammedCore')['all_recursive_layer_geometry_and_texts_match'])

    def test_moved_geometry_or_changed_layer_rejected(self):
        for other in [self.layout(x=1), self.layout(layer=69)]:
            self.assertFalse(compare_cells(self.layout(), other, 'IntegerPLL_ProgrammedCore')['all_recursive_layer_geometry_and_texts_match'])

    def test_changed_pin_label_rejected(self):
        self.assertFalse(compare_cells(self.layout(), self.layout(label='OTHER'), 'IntegerPLL_ProgrammedCore')['all_recursive_layer_geometry_and_texts_match'])


if __name__ == '__main__':
    unittest.main()
