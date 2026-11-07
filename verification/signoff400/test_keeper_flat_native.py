import unittest
from prepare_keeper_flat_native_v2 import normalize

class NativeFlat(unittest.TestCase):
    def source(self,caps):return '.subckt top A\n+ VGND\nX0 private A VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1\nX1 private VGND sky130_fd_pr__res_generic_po l=1 w=1\n'+caps+'\n.ends\n'
    def test_exact_C_and_zero_omission(self):
        model,nodes,r=normalize(self.source('C0 private A 2.01f\nC1 private VGND 0'))
        self.assertIn('C0 '+nodes['private']+' A 2.01f',model);self.assertNotIn('C1 ',model)
        self.assertEqual(r['nonzero_C_preserved'],1);self.assertEqual(r['source_counts']['zero_C_omitted'],1)
    def test_k_suffix_expands_exactly(self):
        model,nodes,r=normalize(self.source('C0 private A 1f').replace('l=0.15 w=1','l=0.15 w=1 ad=5.96385k'))
        self.assertIn('ad=5963.85000',model);self.assertEqual(r['source_counts']['k_suffix_literals_expanded'],1)
    def test_negative_C_rejected(self):
        with self.assertRaisesRegex(ValueError,'negative physical'):normalize(self.source('C0 private A -1f'))
    def test_case_collision_rejected(self):
        with self.assertRaisesRegex(ValueError,'case-colliding conductor'):normalize(self.source('C0 PRIVATE A 1f'))
    def test_nonzero_wire_R_rejected(self):
        with self.assertRaisesRegex(ValueError,'no distributed'):normalize(self.source('R0 private A 1'))
if __name__=='__main__':unittest.main()
