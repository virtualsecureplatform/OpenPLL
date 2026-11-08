import unittest,tempfile
from pathlib import Path
from inventory_keeper_capacitor_boundary_reduction import inventory
class ReductionInventory(unittest.TestCase):
    def run_inventory(self,text):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model';p.write_text(text);return inventory(p,dict(externally_driven_ports={'A':'a','B':'b','RAIL':'v'},observation_only_ports={'PLLOUT':'out'}))
    def test_device_boundary_preserved_and_only_capacitive_ports_classified(self):
        r=self.run_inventory('.subckt root a b v out\nX0 out v __openpll_device\nC0 out a 1f\nC1 out b 3f\nC2 a v 2f\nC3 out v 1f\n.ends\n')
        self.assertEqual(r['direct_device_or_other_ports'],1);self.assertEqual(r['capacitor_only_ports'],2);self.assertEqual(r['aggregate_internal_targets'],1);self.assertEqual(r['forced_boundary_only_C'],1);self.assertEqual(r['projected_forcing_waveforms'],2);self.assertEqual(r['projected_explicit_C_cards'],2);self.assertFalse(r['model_transformed'])
    def test_unknown_card_and_negative_C_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsupported'):self.run_inventory('.subckt root a b v out\nB0 out 0 V={a}\n.ends\n')
        with self.assertRaisesRegex(ValueError,'positive'):self.run_inventory('.subckt root a b v out\nC0 a out -1f\n.ends\n')
if __name__=='__main__':unittest.main()
