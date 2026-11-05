import unittest
from common import ROOT
from nominal_sheet_resistance_v3 import parse, gate_selector_paths


class NominalSheetResistanceV3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech').read_text()

    def test_explicit_nested_gate_alias_paths(self):
        paths = gate_selector_paths(self.text)
        self.assertEqual(paths['scnmos'], ['allpolynonres', 'allfets', 'allnfets', 'scnfet', 'scnmos'])
        values = parse(self.text)
        for target in paths:
            self.assertEqual(values[target], 48200)
        self.assertNotIn('ndiode', values)

    def test_missing_membership_wrong_plane_and_cycles_fail(self):
        changes = [('npd,scnfet,mvnfet', 'npd,mvnfet'),
                   ('-active scnmos,', '-well scnmos,'),
                   ('*poly,allfets,xpc', '*poly,allpolynonres,xpc')]
        for old, new in changes:
            self.assertIn(old, self.text)
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse(self.text.replace(old, new))
