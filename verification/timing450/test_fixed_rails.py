import unittest
from reduce_bbpd_fixed_rails import reduce, verify_ideal_rails


class FixedRailsTests(unittest.TestCase):
    def test_retains_signal_devices_capacitance_and_diode(self):
        text = '''.subckt IntegerPLL_BBPD UP DN REF VPWR VGND
X0 VPWR VGND VPWR VPWR sky130_fd_pr__pfet_01v8_hvt w=1 l=1
X1 UP REF VGND VGND sky130_fd_pr__nfet_01v8 w=1 l=1
X2 VGND REF sky130_fd_pr__diode_pw2nd_05v5 area=4.347e11 perim=2.64e6
C0 UP VPWR 1f
.ends IntegerPLL_BBPD
'''
        result, removed = reduce(text)
        self.assertEqual([r['instance'] for r in removed], ['X0'])
        self.assertIn('X1 UP REF', result)
        self.assertIn('X2 VGND REF', result)
        self.assertIn('C0 UP VPWR', result)

    def test_only_known_models_and_bbpd_top_are_reduced(self):
        text = '''.subckt Other
X0 VPWR VGND VPWR VPWR sky130_fd_pr__pfet_01v8_hvt w=1 l=1
.ends Other
.subckt IntegerPLL_BBPD UP DN REF VPWR VGND
X1 VPWR VGND VPWR VPWR sky130_fd_pr__pfet_01v8_hvt w=1 l=1
X2 VPWR VGND VPWR VPWR unknown_model w=1 l=1
.ends IntegerPLL_BBPD
'''
        result, removed = reduce(text)
        self.assertEqual([r['instance'] for r in removed], ['X1'])
        self.assertIn('X0 VPWR', result)
        self.assertIn('X2 VPWR', result)

    def test_rejects_missing_or_unterminated_top(self):
        for text in ('', '.subckt IntegerPLL_BBPD UP DN\n',
                     '.subckt IntegerPLL_BBPD UP DN\n.ends\n'):
            with self.assertRaises(RuntimeError):
                reduce(text)

    def test_nonideal_sources_and_noise_rejected(self):
        deck = '.param VDD=1.62\n.options device temp=125\nVVPWR VPWR 0 {VDD}\nVVPB VPB 0 {VDD}\nVVGND VGND 0 0\nVVNB VNB 0 0\n.tran 5p 90n\n'
        verify_ideal_rails(deck)
        for text in (deck.replace('VVPWR VPWR 0 {VDD}', 'VVPWR VPWR 0 PULSE(0 1.62 1n 1p 1p 1n 2n)'),
                     deck + '.noise V(UP) VREF\n', deck.replace('VVNB VNB 0 0', ''),
                     deck.replace('VDD=1.62', 'VDD={time}'), deck.replace('temp=125', 'temp={time}')):
            with self.assertRaises(RuntimeError):
                verify_ideal_rails(text)
