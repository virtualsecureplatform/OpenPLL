#!/usr/bin/env python3
import itertools
import unittest

from check_sky130_diode_qualification import BIASES, CORNERS, TEMPERATURES, coverage


class DiodeEvidenceTest(unittest.TestCase):
    def cases(self):
        return [{'corner': c, 'temperature_c': t, 'bias_v': b,
                 'screen_passed': True, 'output_noise_psd_relative_error': 1e-5}
                for c, t, b in itertools.product(CORNERS, TEMPERATURES, BIASES)]

    def test_complete_noise_grid(self):
        coverage(self.cases(), True)

    def test_missing_or_duplicate_case_rejected(self):
        cases = self.cases()
        for damaged in (cases[:-1], cases[:-1] + [cases[0]]):
            with self.assertRaises(ValueError):
                coverage(damaged, True)

    def test_nonfinite_or_failing_measurement_rejected(self):
        for error in (float('nan'), float('inf'), -.01, .001):
            cases = self.cases()
            cases[0]['output_noise_psd_relative_error'] = error
            with self.assertRaises(ValueError):
                coverage(cases, True)

    def test_failed_case_rejected_even_when_error_is_small(self):
        cases = self.cases()
        cases[0]['screen_passed'] = False
        with self.assertRaises(ValueError):
            coverage(cases, True)


if __name__ == '__main__':
    unittest.main()
