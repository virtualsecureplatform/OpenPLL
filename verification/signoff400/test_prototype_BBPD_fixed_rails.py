from fractions import Fraction as F
import unittest
from reduce_prototype_BBPD_fixed_rails import reduce,exact

SOURCE='''.subckt IntegerPLL_BBPD OUT IN VGND VNB VPB VPWR
Rzero IN alias 0
Xfixed VPWR VGND VPWR VPB sky130_fd_pr__pfet_01v8_hvt w=1 l=0.15
Xactive OUT alias VGND VNB sky130_fd_pr__nfet_01v8 w=1.1 l=0.15 ad=0
Csignal OUT alias -0.1f
Cground alias VGND 1f
Crails VPWR VGND 2f
.ends IntegerPLL_BBPD
'''


class FixedRailReductionIntegrity(unittest.TestCase):
    def test_only_fixed_terminal_devices_and_fixed_rail_caps_are_removed(self):
        text,r=reduce(SOURCE)
        self.assertEqual(r['original_primitives'],2)
        self.assertEqual(r['removed_fixed_terminal_primitives'],1)
        self.assertEqual(r['retained_primitives'],1)
        self.assertEqual(r['retained_signed_capacitor_pairs'],2)
        self.assertEqual(r['removed_fixed_rail_capacitor_pairs'],1)
        self.assertTrue(r['retained_cards_and_signed_caps_independently_reparsed_exactly'])
        self.assertFalse(r['power_supply_current_noise_and_nonideal_rails_preserved'])
        self.assertFalse(r['full_vs_reduced_native_waveform_correlation_complete'])
        self.assertIn('sky130_fd_pr__nfet_01v8',text)
        self.assertNotIn('sky130_fd_pr__pfet_01v8_hvt',text)

    def test_nonterminating_fraction_is_not_silently_rounded(self):
        self.assertEqual(F(exact(F(1,10**19))),F(1,10**19))
        with self.assertRaises(ValueError):exact(F(1,3))


if __name__=='__main__':unittest.main()
