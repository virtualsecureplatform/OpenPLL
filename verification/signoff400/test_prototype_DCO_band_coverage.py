import unittest
from review_prototype_DCO_band_coverage import bracket


class BandCoverageTests(unittest.TestCase):
    def test_gap_and_uncertain_endpoint_rejected(self):
        self.assertFalse(bracket([372, 373], [392, 393], 400)['observed_endpoint_bracket'])
        self.assertFalse(bracket([399, 401], [430, 431], 400)['observed_endpoint_bracket'])

    def test_both_polarities_and_strict_headroom(self):
        for low, high in (([390, 391], [430, 431]), ([430, 431], [390, 391])):
            self.assertTrue(bracket(low, high, 400)['observed_endpoint_bracket'])
        self.assertFalse(bracket([390, 400], [430, 431], 400)['observed_endpoint_bracket'])

    def test_invalid_intervals_rejected(self):
        for interval in ([2, 1], [float('nan'), 2], [-1, 2]):
            with self.assertRaises(ValueError):
                bracket(interval, [3, 4], 2.5)
