import unittest
from pathlib import Path
from run_keeper_flat_native_independent import transient_deck as baseline
from run_keeper_flat_native_step50 import transient_deck as control

class Step50(unittest.TestCase):
    def test_only_maximum_timestep_changes(self):
        text='\n'.join(['VRESET RESET_N 0 0','VREF REFCLK 0 0',*[f'V{i} STARTUP_FINE[{i}] 0 0'for i in range(8)],'.options timeint reltol=1e-4','.dc VRESET 0 0 1','.print dc format=csv file=old.csv v(PLLOUT)','.end'])+'\n'
        for code in [8,112,149,247]:
            a,ap=baseline(text,Path('/tmp/control.raw'),code);b,bp=control(text,Path('/tmp/control.raw'),code)
            self.assertEqual(ap,bp)
            self.assertEqual(a.replace('.tran 10p 260n 0 10p','.tran 10p 260n 0 50p'),b)
            self.assertEqual([i for i,(x,y)in enumerate(zip(a.splitlines(),b.splitlines()))if x!=y],[a.splitlines().index('.tran 10p 260n 0 10p')])

if __name__=='__main__':unittest.main()
