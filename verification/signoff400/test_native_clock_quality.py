import unittest
from characterize_native_clock_quality import statistics_from_edges

class ClockQuality(unittest.TestCase):
    def test_constant_period(self):
        r=statistics_from_edges([200+2.5*i for i in range(24)])
        self.assertEqual(r['mean_frequency_MHz'],400);self.assertEqual(r['sampled_period_RMS_deviation_ps'],0);self.assertEqual(r['detrended_sampled_TIE_RMS_ps'],0)
    def test_alternating_periods(self):
        r=statistics_from_edges([0,2.4,5.,7.4,10.])
        self.assertAlmostEqual(r['sampled_period_RMS_deviation_ps'],100);self.assertAlmostEqual(r['sampled_cycle_to_cycle_RMS_ps'],200);self.assertAlmostEqual(r['sampled_period_peak_to_peak_ps'],200)
    def test_invalid_edges_rejected(self):
        for edges in([0,1,2],[0,1,1,2],[0,2,1,3],[0,1,2,float('nan')]):
            with self.subTest(edges=edges),self.assertRaises(ValueError):statistics_from_edges(edges)

if __name__=='__main__':unittest.main()
