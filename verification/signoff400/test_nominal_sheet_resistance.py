import unittest
from nominal_sheet_resistance import parse,SELECTORS
class NominalSheetResistance(unittest.TestCase):
    def fixture(self):return '# Resistances are in milliohms per square\nextract\nstyle ngspice variants (),(orig),(hrhc)\nvariants (),(orig),(si)\n'+''.join('resist '+s+' '+str(i+1)+'\n' for i,s in enumerate(SELECTORS.values()))+'variants (hrhc)\nresist (allm1)/metal1 999\nend\n'
    def test_only_explicit_nominal_variants_and_units_are_used(self):
        r=parse(self.fixture());self.assertEqual(r['metal1'],3);self.assertEqual(len(r),7)
    def test_missing_units_duplicate_and_adjusted_rules_rejected(self):
        base=self.fixture()
        for text in (base.replace('milliohms per square','ohms'),base.replace('variants (hrhc)','resist (allm1)/metal1 125\nvariants (hrhc)'),base.replace('resist (allm1)/metal1 3','resist (allm1)/metal1 3 0.5')):
            with self.assertRaises(ValueError):parse(text)
