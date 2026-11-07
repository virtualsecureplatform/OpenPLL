import unittest
from pathlib import Path
from queue_keeper_flat_native_transient import transient_deck

SOURCE='''* DC reference
.include "checked_model.spice"
VRESET RESET_N 0 0
VREF REFCLK 0 0
VEN PLL_ENABLE 0 0
Vfine STARTUP_FINE[4] 0 1.8
.dc VRESET 0 0 1
.print dc format=csv file=dc.csv v(PLLOUT)
.end
'''
class FlatTransient(unittest.TestCase):
    def test_exact_scope_preservation_and_observation(self):
        text,ports=transient_deck(SOURCE,Path('/tmp/transient.raw'))
        for line in ['.include "checked_model.spice"','VEN PLL_ENABLE 0 0','Vfine STARTUP_FINE[4] 0 1.8']:self.assertIn(line,text)
        self.assertIn('.tran 10p 260n 0 10p',text);self.assertIn('5.1n 1.8',text);self.assertIn('REFCLK 0 PULSE',text)
        self.assertNotIn('.dc ',text);self.assertEqual(ports[0],'PLLOUT');self.assertEqual(len(ports),21)
    def test_changed_or_duplicate_source_rejected(self):
        for source in [SOURCE.replace('.dc VRESET 0 0 1','.dc VRESET 0 1 1'),SOURCE.replace('VRESET RESET_N 0 0','VRESET RESET_N 0 1.8'),SOURCE.replace('VREF REFCLK 0 0','VREF REFCLK 0 0\nVREF2 REFCLK 0 0')]:
            with self.assertRaises(ValueError):transient_deck(source,Path('/tmp/unused.raw'))
if __name__=='__main__':unittest.main()
