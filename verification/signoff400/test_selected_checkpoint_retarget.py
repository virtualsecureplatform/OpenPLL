import unittest
from run_selected_checkpoint_retarget import retarget,interpolate

class Retarget(unittest.TestCase):
    def test_pre_ramp_history_and_both_directions(self):
        for initial,final in((0.,1.8),(1.8,0.)):
            rows=[(0,initial),(.2e-9,initial+.001),(2e-9,initial+.002),(85e-9,initial+.003)]
            changed=retarget(rows,initial,final)
            for t in(0,.1e-9,.2e-9,.5e-9):self.assertAlmostEqual(interpolate(rows,t),interpolate(changed,t),places=15)
            for t in(1.5e-9,10e-9,85e-9):self.assertEqual(interpolate(changed,t),final)
    def test_invalid_level_or_unsettled_source_rejected(self):
        for rows,a,b in(([(0,0),(85e-9,0)],0,0),([(0,0),(85e-9,0)],0,.9),([(0,0),(1e-9,0)],0,1.8),([(0,0),(85e-9,.5)],0,1.8),([(0,0),(85e-9,float('nan'))],0,1.8),([(0,0),(0,0),(85e-9,0)],0,1.8)):
            with self.subTest(rows=rows,a=a,b=b),self.assertRaises(ValueError):retarget(rows,a,b)

if __name__=='__main__':unittest.main()
