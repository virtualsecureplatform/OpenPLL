import unittest
from pathlib import Path
from queue_keeper_flat_native_transient_v2 import transient_deck as queued
from run_keeper_flat_native_independent import transient_deck as independent

class IndependentCapture(unittest.TestCase):
    def test_electrical_protocol_identical_to_queued_version(self):
        text='\n'.join(['VRESET RESET_N 0 0','VREF REFCLK 0 0',*[f'V{i} STARTUP_FINE[{i}] 0 0' for i in range(8)],'.dc VRESET 0 0 1','.print dc format=csv file=old.csv v(PLLOUT)','.end'])+'\n'
        for code in [8,112,149,247]:self.assertEqual(queued(text,Path('/tmp/capture.raw'),code),independent(text,Path('/tmp/capture.raw'),code))

if __name__=='__main__':unittest.main()
