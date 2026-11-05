import tempfile
import unittest
from pathlib import Path
import characterize_bbpd as bbpd

class LoadedBBPD(unittest.TestCase):
    def test_pulses_and_slew(self):
        rows=[]
        for index in range(901):
            t=index*.1e-9
            def pulse(offset):
                local=(t-offset)%40e-9
                if local<1e-9:return local/1e-9*1.8
                if local<3e-9:return 1.8
                if local<4e-9:return (4e-9-local)/1e-9*1.8
                return 0.
            rows.append([index,t,0.,0.,pulse(10e-9),pulse(10.05e-9),0.])
        measured=bbpd.measure(rows,1.8)
        for waveform in measured.values():
            self.assertTrue(waveform['complete_two_pulses'])
            for width in waveform['high_pulse_widths_ns']:self.assertAlmostEqual(width,3.,places=6)
            for width in waveform['rising_slew_20_80_ns']:self.assertAlmostEqual(width,.6,places=6)
        for row in rows:row[4]*=.1
        self.assertFalse(bbpd.measure(rows,1.8)['BBPD[0]']['complete_two_pulses'])
    def test_incomplete_and_nonfinite_waveform_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wave.prn'
            for text in ('Index TIME\n0 0 0 0 0 0 0\nEnd of Xyce(TM) Simulation\n',
                         'Index TIME\n0 0 0 0 nan 0 0\nEnd of Xyce(TM) Simulation\n',
                         'Index TIME\n0 0 0 0 0 0 0\n1 0 0 0 0 0 0\nEnd of Xyce(TM) Simulation\n'):
                p.write_text(text)
                with self.assertRaises(RuntimeError):bbpd.read_rows(p)
    def test_deck_keeps_corner_temperature_and_phase(self):
        text=bbpd.deck(Path('/pdk'),Path('/macro'), 'sf',1.95,-40,-50,200,[.19,.17])
        self.assertIn('sky130.lib.spice" sf',text)
        self.assertIn('.options device temp=-40',text)
        self.assertIn('9.95n 200p 200p',text)
        self.assertIn('CUP BBPD[1] 0 0.17p',text)
        self.assertNotIn('.temp ',text)
        for supply in (2.,0.):
            with self.assertRaises(RuntimeError):bbpd.deck(Path('/pdk'),Path('/macro'),'tt',supply,27,50,20,[.19,.17])
    def test_hash_guard(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_text('original');hashes={str(p):bbpd.sha(p)}
            bbpd.verify(hashes);p.write_text('changed')
            with self.assertRaises(RuntimeError):bbpd.verify(hashes)

if __name__=='__main__':unittest.main()
