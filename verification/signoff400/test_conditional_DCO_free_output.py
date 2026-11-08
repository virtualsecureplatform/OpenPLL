import unittest
from export_keeper_conditional_DCO_v2 import partition

class FreeOutputTests(unittest.TestCase):
    def source(self):return '.subckt top IN VGND OUT\nX1 OUT IN VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1\nX2 ext OUT VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1\nC1 OUT ext 2f\n.ends\n'
    def test_omitted_receiver_forbids_free_output(self):
        with self.assertRaises(ValueError):partition(self.source(),{'X1'},['OUT'])
    def test_retained_receiver_allows_observation_only_port(self):
        text,m=partition(self.source(),{'X1','X2'},['OUT'])
        self.assertEqual(m['observation_only_ports'],['OUT'])
        self.assertNotIn('OUT',m['externally_driven_ports'])
        self.assertIn('OUT',m['boundary_ports'])
        self.assertIn('C1 OUT ext 2f',text)
    def test_coupling_to_exterior_does_not_force_output(self):
        text,m=partition(self.source().replace('X2 ext OUT VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1\n',''),{'X1'},['OUT'])
        self.assertIn('ext',m['externally_driven_ports'])
        self.assertNotIn('OUT',m['externally_driven_ports'])

if __name__=='__main__':unittest.main()
