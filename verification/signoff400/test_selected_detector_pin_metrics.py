import tempfile,unittest
from pathlib import Path
from capture_selected_detector_pins import metrics


class PinMetricsTests(unittest.TestCase):
    def test_known_ramp_and_truncated_waveform(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pin.pwl';p.write_text('0 0\n1e-9 0\n2e-9 1.8\n260e-9 1.8\n')
            r=metrics(p)
            self.assertAlmostEqual(r['minimum_10_90_rise_slew_ps'],800)
            self.assertEqual(r['rising_logic_edges'],1)
            p.write_text('0 0\n2e-9 1.8\n')
            with self.assertRaises(ValueError):metrics(p)


if __name__=='__main__':unittest.main()
