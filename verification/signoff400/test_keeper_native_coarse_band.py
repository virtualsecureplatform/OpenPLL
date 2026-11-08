import unittest
from pathlib import Path
from run_keeper_native_BSIM_coarse_band import transient_deck
from run_keeper_flat_native_independent import transient_deck as original
class CoarseBand(unittest.TestCase):
    def source(self):
        return '\n'.join(['* fixture','.include model.spice','VRESET RESET_N 0 0','Vref REFCLK 0 0','Venable PLL_ENABLE 0 0',*[f'Vc{i} STARTUP_COARSE[{i}] 0 '+('1.8' if 20&(1<<i) else '0') for i in range(6)],*[f'Vf{i} STARTUP_FINE[{i}] 0 0' for i in range(8)],'.dc VRESET 0 0 1','.print dc format=csv file=dc.csv V(VPWR)','.end'])+'\n'
    def test_original_coarse20_deck_unchanged(self):
        for fine in [8,149,247]:self.assertEqual(transient_deck(self.source(),Path('/tmp/output.raw'),fine,20,10),original(self.source(),Path('/tmp/output.raw'),fine))
    def test_only_coarse_bits_and_requested_step_change(self):
        for fine in [8,149,247]:
            base,_=original(self.source(),Path('/tmp/output.raw'),fine)
            for coarse in [0,20,21,47]:
                for step in [10,50]:
                    text,_=transient_deck(self.source(),Path('/tmp/output.raw'),fine,coarse,step)
                    rows=[l.split() for l in text.splitlines() if len(l.split())==4 and l.split()[1].startswith('STARTUP_COARSE[')]
                    self.assertEqual([r[3] for r in rows],['1.8' if coarse&(1<<i) else '0' for i in range(6)])
                    keep=lambda t:[l for l in t.splitlines() if 'STARTUP_COARSE[' not in l]
                    self.assertEqual(keep(text),keep(base.replace('.tran 10p 260n 0 10p',f'.tran 10p 260n 0 {step}p')))
    def test_invalid_or_incomplete_programming_rejected(self):
        for coarse in [-1,48]:
            with self.assertRaisesRegex(ValueError,'coarse code'):transient_deck(self.source(),Path('/tmp/output.raw'),149,coarse,10)
        with self.assertRaisesRegex(ValueError,'all six'):transient_deck(self.source().replace('Vc0 STARTUP_COARSE[0] 0 0\n',''),Path('/tmp/output.raw'),149,21,10)
if __name__=='__main__':unittest.main()
