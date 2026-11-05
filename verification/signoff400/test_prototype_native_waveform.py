import unittest
from assess_prototype_native_waveform import assess


class NativeWaveformControls(unittest.TestCase):
    def test_late_period_change_is_included(self):
        # Rising crossings at 0.5, 2.5, 4.5, 7.5: the last cycle is slower.
        points=[(0,0),(1,2),(2,0),(3,2),(4,0),(5,2),(7,0),(8,2),(9,0)]
        r=assess(points,0,9,2)
        self.assertEqual(r['complete_measured_cycles'],3)
        self.assertEqual(r['observed_period_interval_s'],[2,3])
        self.assertEqual(r['observed_frequency_interval_hz'],[1/3,1/2])
        self.assertAlmostEqual(r['average_frequency_hz'],3/7)
        self.assertFalse(r['numerical_convergence_uncertainty_included'])

    def test_truncated_window_or_too_few_periods_rejected(self):
        points=[(0,0),(1,2),(2,0),(3,2)]
        for end in (3,4):
            with self.assertRaises(ValueError):assess(points,0,end,2)


if __name__=='__main__':unittest.main()
