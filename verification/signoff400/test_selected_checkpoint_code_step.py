import unittest
from run_selected_checkpoint_code_step import pulse,interpolate

class Pulse(unittest.TestCase):
    def test_exact_history_preserved_outside_pulse(self):
        rows=[(0,1.8),(5e-9,0),(25e-9,.001),(40e-9,.002),(70e-9,.003),(85e-9,.004)]
        changed=pulse(rows)
        for t in(0,1e-9,10e-9,25e-9,29e-9,61e-9,65e-9,85e-9):self.assertAlmostEqual(interpolate(rows,t),interpolate(changed,t),places=15)
        for t in(31e-9,40e-9,60e-9):self.assertEqual(interpolate(changed,t),1.8)
    def test_invalid_or_active_baseline_rejected(self):
        for rows in([],[(0,0),(60e-9,0)],[(0,0),(40e-9,1.8),(85e-9,0)],[(0,0),(40e-9,float('nan')),(85e-9,0)],[(0,0),(40e-9,0),(40e-9,0),(85e-9,0)]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):pulse(rows)

if __name__=='__main__':unittest.main()
