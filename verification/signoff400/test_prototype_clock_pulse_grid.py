import tempfile
from pathlib import Path
import unittest
from run_prototype_clock_pulse_grid import assess,waveform


class ClockPulseGrid(unittest.TestCase):
    def test_capture_and_measured_pulse_width(self):
        rows=[(0,0,0),(4.5e-9,0,0),(5e-9,0,0),(5.9e-9,0,0),(6.1e-9,0,1.8),
              (6.3e-9,1.8,1.8),(6.5e-9,1.8,0),(12e-9,1.8,0),(13e-9,1.8,0),(14e-9,1.8,0)]
        result=assess(rows,'high',0,1)
        self.assertTrue(result['full_output_trace_capture_verified'])
        self.assertAlmostEqual(result['observed_clock_pulse_width_ps'],400)
        glitch=rows[:7]+[(7e-9,0,0),(8e-9,1.8,0)]+rows[7:]
        self.assertFalse(assess(glitch,'high',0,1)['full_output_trace_capture_verified'])

    def test_incomplete_nonfinite_and_wrong_columns_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wave.dat'
            good='time v(q0) v(clk0)\n0 0 0\n1.4e-8 1.8 0\n'
            p.write_text(good);self.assertEqual(len(waveform(p,1)),2)
            for bad in (good.replace('1.4e-8','1.3e-8'),good.replace('1.8','nan'),good.replace('v(q0)','v(q1)')):
                p.write_text(bad)
                with self.assertRaises(ValueError):waveform(p,1)


if __name__=='__main__':unittest.main()
