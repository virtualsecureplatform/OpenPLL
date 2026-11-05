from fractions import Fraction
import unittest
from common import ROOT
from nominal_sheet_resistance_v2 import parse


class NominalSheetResistanceV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech').read_text()

    def test_documented_canonical_materials_and_aliases(self):
        values = parse(self.text)
        self.assertEqual(len(values), 13)
        self.assertEqual(values['ndiff'], Fraction(120000))
        self.assertEqual(values['nsubdiff'], values['ndiff'])
        self.assertEqual(values['pdiff'], Fraction(197000))
        self.assertEqual(values['psubdiff'], values['pdiff'])
        self.assertEqual(values['pwell'], Fraction(4400000))
        self.assertEqual(values['nwell'], Fraction(950000))
        self.assertNotIn('scnmos', values)
        self.assertNotIn('scpmoshvt', values)

    def test_unknown_alias_or_plane_fails(self):
        for old, new in [('nnd,nsd,ntap', 'nnd,unknown,ntap'),
                         ('active nsubdiff,', 'well nsubdiff,')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse(self.text.replace(old, new))

    def test_ambiguous_adjusted_missing_and_nonpositive_fail(self):
        needle = 'resist (nwell)/well             950000'
        self.assertIn(needle, self.text)
        for replacement in ['', needle+' 0.5', needle+'\n'+needle,
                            'resist (nwell)/well 0']:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                parse(self.text.replace(needle, replacement, 1))
