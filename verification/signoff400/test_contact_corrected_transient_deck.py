import unittest
from pathlib import Path
from contact_corrected_transient_deck import transient_deck

class CorrectedDeck(unittest.TestCase):
    def source(self):
        return '\n'.join(['VRESET RESET_N 0 0','VR REFCLK 0 0','VE PLL_ENABLE 0 0',
          *[f'VF{i} STARTUP_FINE[{i}] 0 0' for i in range(8)],
          *[f'VC{i} STARTUP_COARSE[{i}] 0 0' for i in range(6)],
          '.dc VRESET 0 0 1','.print dc format=csv file=dc.csv V(PLLOUT)','.end'])+'\n'
    def test_reset_capture_and_static_codes(self):
        deck,ports=transient_deck(self.source(),Path('/tmp/capture.prn'),134,23)
        self.assertIn('.tran 10p 340n 0 10p',deck)
        self.assertIn('PWL(0 0 80n 0 80.1n 1.8 340n 1.8)',deck)
        self.assertIn('format=std precision=17',deck)
        self.assertIn('REFCLK 0 PULSE',deck);self.assertEqual(ports[0],'PLLOUT')
        for bus,width,code in [('FINE',8,134),('COARSE',6,23)]:
            for i in range(width):
                expected='1.8' if code&(1<<i) else '0'
                self.assertTrue(any(s.split()[1:]==[f'STARTUP_{bus}[{i}]','0',expected] for s in deck.splitlines()))
    def test_missing_duplicate_or_enabled_sources_rejected(self):
        source=self.source()
        for text in [source.replace('VE PLL_ENABLE 0 0',''),source+'VE2 PLL_ENABLE 0 0\n',source.replace('VE PLL_ENABLE 0 0','VE PLL_ENABLE 0 1.8')]:
            with self.assertRaises(ValueError):transient_deck(text,Path('/tmp/capture.prn'),134,23)

if __name__=='__main__':unittest.main()
