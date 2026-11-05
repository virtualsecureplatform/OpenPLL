import unittest
from characterize_selected_detector_response import pair_phases,cycle_capture,rise_slews

class DetectorResponseTests(unittest.TestCase):
    def test_feedback_before_reference_is_preserved(self):
        self.assertEqual(pair_phases([20,60],[19,59]),[(20,19),(60,59)])
        with self.assertRaises(ValueError):pair_phases([20],[19,21])
        with self.assertRaises(ValueError):pair_phases([20,21],[20])
    def test_both_toggle_directions_count_as_captures(self):
        result=cycle_capture(dict(rising_ns=[20,60],falling_ns=[40]),
                             dict(rising_ns=[20.5],falling_ns=[60.5]),10,80)
        self.assertEqual(result['event_toggles'],2)
        self.assertTrue(result['one_toggle_per_detector_rise'])
        self.assertEqual(result['capture_latencies_ps'],[500,500])
    def test_noncausal_capture_fails(self):
        self.assertFalse(cycle_capture(dict(rising_ns=[20]),dict(rising_ns=[19],falling_ns=[]),10,30)['one_toggle_per_detector_rise'])
    def test_slew_excludes_recrossed_low_threshold(self):
        rows=[[0,0],[1e-9,.2],[2e-9,0],[3e-9,.2],[4e-9,1.8]]
        slews=rise_slews(rows,1)
        self.assertEqual(len(slews),1)
        self.assertGreater(slews[0],900)

if __name__=='__main__':unittest.main()
