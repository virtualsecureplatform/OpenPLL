#!/usr/bin/env python3
import unittest
from translate_sky130_diode import translate


class ExtractedDiodeTranslationTest(unittest.TestCase):
    def test_preserves_nodes_and_other_devices(self):
        text = '.subckt DCO VDD GND CTRL\nR1 CTRL VDD 50\nX49 GND CTRL sky130_fd_pr__diode_pw2nd_05v5 perim=2.64e6 area=4.347e11\n.ends\n'
        translated, count = translate(text)
        self.assertEqual(count, 1)
        self.assertIn('R1 CTRL VDD 50\n', translated)
        self.assertIn('X49 GND CTRL openpll_pw2nd_qualified_geometry\n', translated)

    def test_rejects_unqualified_geometry_and_ambiguous_instances(self):
        prefix = 'X49 GND CTRL sky130_fd_pr__diode_pw2nd_05v5 '
        for params in ('perim=2.64e6 area=4e11', 'perim=3e6 area=4.347e11',
                       'area=4.347e11', 'area=4.347e11 area=4.347e11',
                       'perim={P} area=4.347e11'):
            with self.assertRaises(ValueError):
                translate(prefix + params + '\n')

    def test_rejects_netlist_without_supported_device(self):
        with self.assertRaises(ValueError):
            translate('.subckt DCO A B\nR1 A B 100\n.ends\n')


if __name__ == '__main__':
    unittest.main()
