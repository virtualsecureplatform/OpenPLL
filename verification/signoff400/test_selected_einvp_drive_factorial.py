import unittest
from check_selected_einvp_drive_factorial import quiet_cut


class DriveTests(unittest.TestCase):
    text='.subckt selected_einvp_cut a te vdd\nXflat1 z a n vdd leaf\nXflat2 n te 0 0 leaf\nCcross z a 1e-15\nCinternal z n 2e-15\n.ends selected_einvp_cut\n'
    initial={'a':.3,'te':0.,'vdd':1.8}

    def test_capacitor_control_preserves_gate_connections(self):
        result,counts=quiet_cut(self.text,{'z','n'},{'a','te'},self.initial,True,False)
        self.assertIn('Xflat1 z a n vdd leaf',result)
        self.assertIn('Ccross z __openpll_quiet_0 1e-15',result)
        self.assertIn('Cinternal z n 2e-15',result)
        self.assertEqual(counts['capacitor_endpoints'],1)
        self.assertEqual(counts['external_gate_endpoints'],0)

    def test_gate_control_preserves_capacitor_connections(self):
        result,counts=quiet_cut(self.text,{'z','n'},{'a','te'},self.initial,False,True)
        self.assertIn('Ccross z a 1e-15',result)
        self.assertIn('Xflat1 z __openpll_quiet_0 n vdd leaf',result)
        self.assertEqual(counts['external_gate_endpoints'],2)

    def test_combined_control_shares_initial_voltage_source(self):
        result,counts=quiet_cut(self.text,{'z','n'},{'a','te'},self.initial,True,True)
        self.assertEqual(counts['quiet_boundary_nodes'],2)
        self.assertEqual(result.count('Vquiet'),2)

    def test_missing_initial_voltage_rejected(self):
        with self.assertRaisesRegex(ValueError,'initial boundary'):
            quiet_cut(self.text,{'z','n'},{'a','te'},{},True,False)


if __name__=='__main__':unittest.main()
