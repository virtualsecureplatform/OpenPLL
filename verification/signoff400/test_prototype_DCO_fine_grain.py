from pathlib import Path
import unittest
from prepare_prototype_DCO_fine_grain_schematic import revise as spice_revise
from build_prototype_DCO_fine_grain_candidate import revise as rtl_revise

class FineGrainMapping(unittest.TestCase):
    def test_each_code_controls_one_alternating_stage_load(self):
        source=Path('sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v')
        text=rtl_revise(source.read_text());lines=[line for line in text.splitlines() if 'sky130_fd_sc_hd__einvp_1 fine_' in line]
        self.assertEqual(len(lines),510)
        for code in range(255):
            self.assertEqual(text.count(f'.TE(DCO_THERM[{code}])'),1)
            pair=lines[2*code:2*code+2]
            self.assertIn(f'.TE(DCO_THERM[{code}])',pair[code%2])
            self.assertIn('.TE(tie_lo)',pair[1-code%2])
        self.assertEqual(text.count('sky130_fd_sc_hd__einvn_1 drive_'),110)
    def test_schematic_and_RTL_control_mapping_agree(self):
        text=''.join(f'Xfine_{i} DCO_THERM[{i//2}] ring{1+i%2} unused{i} cell\n' for i in range(510))
        result=spice_revise(text).splitlines()
        self.assertEqual(sum(line.split()[1]=='VGND' for line in result),255)
        for i,line in enumerate(result):self.assertEqual(line.split()[1],'VGND' if i%2!=(i//2)%2 else f'DCO_THERM[{i//2}]')

if __name__=='__main__':unittest.main()
