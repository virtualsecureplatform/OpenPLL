import copy
import unittest
from build_prototype_DCO_rc import build
from prototype_spef_v2 import parse
from test_prototype_spef import FIXTURE

SOURCE = '.subckt leaf A Z\nCcell A Z 1f\n.ends leaf\n.subckt top input output VGND\nXphysical input output leaf\nCmacro input output 2f\n.ends top\n'

class HierarchicalRCControls(unittest.TestCase):
    def test_cell_capacitance_retained_and_macro_capacitance_replaced(self):
        model, counts = build(SOURCE, 'top', parse(FIXTURE), {'cell':'physical'})
        self.assertIn('Ccell A Z 1f', model)
        self.assertNotIn('Cmacro', model)
        self.assertEqual(counts['rewired_cell_pins'], 1)
        self.assertEqual(counts['wire_resistors'], 1)
        self.assertEqual(counts['wire_capacitors'], 2)

    def test_mirrored_coupling_emitted_once(self):
        spef = parse(FIXTURE)
        cap = {'nodes':['input','cell:A'], 'farads':'1/1000000000000'}
        spef['nets'][0]['capacitors'].append(cap)
        spef['nets'].append({'name':'other', 'connections':[], 'resistors':[], 'capacitors':[copy.deepcopy(cap)]})
        # The binding checker correctly rejects a conductor without terminals;
        # use an independently bound second conductor for the mirrored record.
        spef['nets'][1]['connections']=[{'kind':'P','node':'output','direction':'O'}]
        model, counts = build(SOURCE, 'top', spef, {'cell':'physical'})
        self.assertEqual(counts['mirrored_coupling_pairs'], 1)
        self.assertEqual(counts['wire_capacitors'], 3)
        spef['nets'][1]['capacitors'][0]['farads']='2/1000000000000'
        with self.assertRaisesRegex(ValueError, 'mirrored'):build(SOURCE, 'top', spef, {'cell':'physical'})

    def test_zero_resistance_and_unbound_pins_rejected(self):
        spef = parse(FIXTURE)
        spef['nets'][0]['resistors'][0]['ohms']='0'
        with self.assertRaisesRegex(ValueError, 'alias'):build(SOURCE, 'top', spef, {'cell':'physical'})
        with self.assertRaisesRegex(ValueError, 'binding'):build(SOURCE, 'top', parse(FIXTURE), {})

if __name__ == '__main__':unittest.main()
