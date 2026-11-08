import unittest
from prepare_keeper_conditional_native import safe_ports

class PortNamingTests(unittest.TestCase):
    def interface(self):return dict(boundary_ports=['PLLOUT','hier.n[2]','a#'],observation_only_ports=['PLLOUT'],externally_driven_ports=['hier.n[2]','a#'])
    def source(self):return '.subckt top PLLOUT hier.n[2] a#\nX1 PLLOUT hier.n[2] a# a# sky130_fd_pr__nfet_01v8 w=1 l=0.15\nC1 PLLOUT a# 2f\n.ends top\n'
    def test_unusual_names_reversibly_mapped(self):
        text,m=safe_ports(self.source(),self.interface())
        self.assertIn('C1 '+m['PLLOUT']+' '+m['a#']+' 2f',text)
        self.assertEqual(len(set(m.values())),3)
    def test_forced_output_rejected(self):
        i=self.interface();i['externally_driven_ports'].append('PLLOUT')
        with self.assertRaises(ValueError):safe_ports(self.source(),i)
    def test_generated_namespace_collision_rejected(self):
        with self.assertRaises(ValueError):safe_ports(self.source().replace('X1 PLLOUT','X1 openpll_boundary_0'),self.interface())

if __name__=='__main__':unittest.main()
