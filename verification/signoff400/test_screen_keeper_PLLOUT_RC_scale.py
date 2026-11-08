import unittest,tempfile
from pathlib import Path
from screen_keeper_PLLOUT_RC_scale import screen
class Scale(unittest.TestCase):
    def run_screen(self,text):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'circuit';p.write_text(text);return screen(p)
    def test_parallel_edges_do_not_become_effective_resistance_claim(self):
        r=self.run_screen('R0 PLLOUT a 100\nR1 PLLOUT a 50\nR2 a b 20\nC0 PLLOUT VGND 2f\nC1 a b 1f\nC2 other VGND 99f\n')
        self.assertEqual(r['maximum_shortest_series_path_R_ohm'],70);self.assertEqual(r['sum_wire_R_ohm'],170);self.assertEqual(r['incident_explicit_C_F'],3e-15);self.assertEqual(r['intra_component_explicit_C_F'],1e-15);self.assertFalse(r['timing_or_phase_bound_qualified'])
    def test_disconnected_or_negative_network_rejected(self):
        with self.assertRaisesRegex(ValueError,'one PLLOUT'):self.run_screen('R0 PLLOUT a 1\nR1 b c 2\n')
        with self.assertRaisesRegex(ValueError,'nonnegative'):self.run_screen('R0 PLLOUT a 1\nC0 a VGND -1f\n')
if __name__=='__main__':unittest.main()
