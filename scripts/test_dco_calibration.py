from pathlib import Path
import tempfile
import unittest

from dco_calibration import assess, measure


class CalibrationTest(unittest.TestCase):
    def samples(self):
        return {variant: {code: dict(mhz=100+code*.02,half_window_difference_mhz=0)
                          for code in [0,1,2]}
                for variant in ['baseline','tolerance','step','settling']}

    def test_both_ppm_and_local_lsb_limits(self):
        data = self.samples()
        self.assertTrue(assess(data,100)['convergence_passed'])
        # 60 ppm passes the 100 ppm bound but fails quarter-LSB (50 ppm).
        data['baseline'][1]['mhz'] += .006
        self.assertFalse(assess(data,100)['convergence_passed'])
        # At 25 MHz the ppm bound is tighter than the LSB bound.
        data = self.samples()
        data['step'][1]['mhz'] += .003
        self.assertFalse(assess(data,25)['convergence_passed'])

    def test_settling_and_missing_evidence(self):
        data = self.samples()
        data['baseline'][0]['half_window_difference_mhz'] = .1
        self.assertFalse(assess(data,100)['convergence_passed'])
        del data['step']
        with self.assertRaises(ValueError): assess(data,100)

    def test_frequency_over_full_window_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'wave.prn'
            # Symmetric ramps crossing VDD/2 every 10 ns.
            rows = [(0,0)]
            for i in range(12):
                rows.extend([(i*10+1,0),(i*10+2,1.8),(i*10+6,1.8),(i*10+7,0)])
            rows.append((120,0))
            path.write_text(''.join(f'{i} {t*1e-9:.12g} {v}\n' for i,(t,v) in enumerate(rows)))
            self.assertAlmostEqual(measure(path,10,120,1.8)['mhz'],100)
            with self.assertRaisesRegex(ValueError,'incomplete'): measure(path,10,130,1.8)
            with self.assertRaisesRegex(ValueError,'at least'): measure(path,100,120,1.8)


if __name__ == '__main__': unittest.main()
