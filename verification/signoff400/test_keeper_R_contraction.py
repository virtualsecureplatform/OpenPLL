import unittest
from audit_keeper_native_R_contraction import compare

class NativeContraction(unittest.TestCase):
    def base(self):return '.subckt top G D S B\nX1 D G S B sky130_fd_pr__nfet_01v8 ad=2 as=3 pd=4 ps=5 w=1 l=0.15\nC1 D S 2f\n.ends\n'
    def test_split_wire_recovers_device_and_summed_C(self):
        r=self.base().replace('X1 D','R1 D internal 12\nX1 internal').replace('C1 D S 2f','C1 D S 1f\nC2 internal S 1f')
        self.assertTrue(compare(self.base(),r)['exact_device_and_C_contraction_verified'])
    def test_changed_C_rejected(self):
        self.assertFalse(compare(self.base(),self.base().replace('2f','3f'))['exact_aggregated_C_match'])
    def test_changed_property_rejected(self):
        self.assertFalse(compare(self.base(),self.base().replace('w=1','w=2'))['primitive_multisets_match'])
    def test_diffusion_reversal_preserves_terminal_parameters(self):
        r=self.base().replace('X1 D G S B','X1 S G D B').replace('ad=2 as=3 pd=4 ps=5','ad=3 as=2 pd=5 ps=4')
        self.assertTrue(compare(self.base(),r)['primitive_multisets_match'])
    def test_short_between_original_conductors_rejected(self):
        self.assertFalse(compare(self.base(),self.base().replace('.ends','R1 D S 1\n.ends'))['exact_device_and_C_contraction_verified'])

if __name__=='__main__':unittest.main()
