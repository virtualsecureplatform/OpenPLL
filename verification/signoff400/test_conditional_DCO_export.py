import unittest
from export_keeper_conditional_DCO import partition

class ConditionalExportTests(unittest.TestCase):
    def source(self):return '.subckt top IN VPWR VGND OUT\nX1 OUT IN VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1\nX2 ext OUT VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1\nC1 OUT ext 2f\nC2 IN VGND 3f\nC3 ext VGND 4f\n.ends\n'
    def test_external_load_and_coupling_become_ports(self):
        text,m=partition(self.source(),{'X1'})
        self.assertEqual(m['boundary_ports'],['IN','OUT','VGND','ext'])
        self.assertEqual(m['interior_nodes'],[])
        self.assertIn('C1 OUT ext 2f',text);self.assertNotIn('C3 ext VGND 4f',text)
        self.assertFalse(m['standalone_executable']);self.assertFalse(m['default_boundary_sources_added'])
    def test_missing_selected_device_rejected(self):
        with self.assertRaises(ValueError):partition(self.source(),{'X9'})
    def test_negative_capacitor_rejected(self):
        with self.assertRaises(ValueError):partition(self.source().replace('2f','-2f'),{'X1'})

if __name__=='__main__':unittest.main()
