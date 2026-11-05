from pathlib import Path
import tempfile
import unittest

from dco_calibration import assess, assess_interpolation, measure


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

    def test_nonfinite_and_invalid_calibration_values_are_rejected(self):
        for variant in ['baseline', 'tolerance', 'step', 'settling']:
            for field, values in [('mhz', [float('nan'), float('inf'), 0, -1]),
                                  ('half_window_difference_mhz', [float('nan'), float('inf'), -1])]:
                for value in values:
                    data = self.samples()
                    data[variant][1][field] = value
                    with self.assertRaisesRegex(ValueError, 'calibration samples'):
                        assess(data, 100)
        for target in [float('nan'), float('inf'), 0, -1]:
            with self.assertRaisesRegex(ValueError, 'target frequency'):
                assess(self.samples(), target)

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

    def test_interpolation_requires_every_code_and_local_accuracy(self):
        spec = {"fine_code_min": 8, "fine_code_max": 12,
                "calibration_error_ppm": 100,
                "calibration_error_local_lsb": 0.25}
        reference = {code: {"mhz": 500 + (code - 8) * .1,
                            "half_window_difference_mhz": 0}
                     for code in (8, 9, 11, 12)}
        holdouts = {10: {"mhz": 500.2, "half_window_difference_mhz": 0}}
        self.assertTrue(assess_interpolation(
            reference, holdouts, [8, 12], 500, spec)["interpolation_validated"])
        holdouts[10]["mhz"] = 500.23
        self.assertFalse(assess_interpolation(
            reference, holdouts, [8, 12], 500, spec)["interpolation_validated"])
        with self.assertRaisesRegex(ValueError, 'every fine code'):
            assess_interpolation(reference, {}, [8, 12], 500, spec)
        holdouts[10]['mhz'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'calibration samples'):
            assess_interpolation(reference, holdouts, [8, 12], 500, spec)


if __name__ == '__main__': unittest.main()
