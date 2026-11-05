import unittest
from pathlib import Path
from build_prototype_DCO_drive_trim_candidate import revise

class DriveTrimLayoutSource(unittest.TestCase):
    def test_matches_native_architecture(self):
        source=Path('sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v')
        text=revise(source.read_text())
        self.assertEqual(text.count('sky130_fd_sc_hd__einvn_1 drive_'),110)
        self.assertEqual(text.count('sky130_fd_sc_hd__einvp_1 fine_'),510)
        self.assertEqual(text.count('sky130_fd_sc_hd__einvp_1 coarse_inv_'),47)
        self.assertEqual(text.count('.TE_B(tie_lo)'),16)
        for i in range(255):
            self.assertEqual(text.count(f'.TE(DCO_THERM[{i}])'),2)
        self.assertIn('.B(ring[2]), .Y(ring[0])',text)
        self.assertIn('.A(ring[2]), .X(PLLOUT)',text)

if __name__=='__main__':unittest.main()
