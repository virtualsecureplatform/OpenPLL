import unittest
from pathlib import Path
from queue_keeper_flat_native_transient_v2 import transient_deck

class CaptureDeckTests(unittest.TestCase):
    def source(self):
        return '\n'.join(['VRESET RESET_N 0 0','VREF REFCLK 0 0',*[f'V{i} STARTUP_FINE[{i}] 0 0' for i in range(8)],'.dc VRESET 0 0 1','.print dc format=csv file=old.csv v(PLLOUT)','.end'])+'\n'
    def test_selected_code_and_all_node_capture(self):
        text,ports=transient_deck(self.source(),Path('/tmp/capture.raw'),149)
        bits={int(f[1][13:-1]):float(f[3]) for line in text.splitlines() if len(f:=line.split())==4 and f[1].startswith('STARTUP_FINE[')}
        self.assertEqual(sum((v>0.9)<<i for i,v in bits.items()),149)
        self.assertIn(' V(*)\n',text);self.assertEqual(len(ports),21)
        self.assertIn('.tran 10p 260n 0 10p',text)
    def test_missing_bit_rejected(self):
        with self.assertRaises(ValueError):transient_deck(self.source().replace('V7 STARTUP_FINE[7] 0 0\n',''),Path('/tmp/x'),149)
    def test_outside_headroom_rejected(self):
        for code in [7,248]:
            with self.assertRaises(ValueError):transient_deck(self.source(),Path('/tmp/x'),code)

if __name__=='__main__':unittest.main()
