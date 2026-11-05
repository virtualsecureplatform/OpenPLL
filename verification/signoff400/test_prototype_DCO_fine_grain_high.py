from pathlib import Path
import unittest
from prepare_prototype_DCO_fine_grain_schematic_v2 import revise as spice_revise
from build_prototype_DCO_fine_grain_candidate_v2 import revise as rtl_revise

class RetainedFineLoad(unittest.TestCase):
    def test_inverted_thermometer_retains_full_low_code_load(self):
        source=Path('sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v')
        text=rtl_revise(source.read_text());loads=[line for line in text.splitlines() if 'sky130_fd_sc_hd__einvp_1 fine_' in line]
        self.assertEqual(len(loads),510)
        self.assertEqual(sum('.TE(tie_hi)' in line for line in loads),255)
        self.assertEqual(sum('.TE(tie_lo)' in line for line in loads),0)
        for code in range(255):self.assertEqual(text.count(f'.TE(DCO_THERM[{code}])'),1)
        for fine in (0,8,128,247,255):
            variable=sum(not (fine>bit) for bit in range(255))
            self.assertEqual(255+variable,510-fine)
    def test_schematic_uses_positive_supply_on_fixed_alternating_loads(self):
        text=''.join(f'Xfine_{i} DCO_THERM[{i//2}] ring{1+i%2} unused{i} cell\n' for i in range(510))
        lines=spice_revise(text).splitlines()
        for i,line in enumerate(lines):self.assertEqual(line.split()[1],'VPWR' if i%2!=(i//2)%2 else f'DCO_THERM[{i//2}]')

if __name__=='__main__':unittest.main()
