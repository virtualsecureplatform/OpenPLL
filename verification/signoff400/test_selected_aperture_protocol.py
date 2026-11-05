import unittest
from selected_feedback_aperture_shapes import delayed_reference
from bounded_clock_sources import crossings
from characterize_selected_detector_response_v3 import nearest


class ApertureProtocolTest(unittest.TestCase):
    def test_reference_hold_keeps_recorded_active_edge_shape(self):
        rows=[(0,0),(1,0),(2,1.8),(3,0)]
        result=delayed_reference(rows,-4,7)
        self.assertEqual(result[0],(0,0));self.assertEqual(result[1],(4,0))
        self.assertEqual(crossings(result,.9),[(t+4,d) for t,d in crossings(rows,.9)])
        self.assertEqual(result[-1],(7,0))

    def test_uncovered_active_window_and_high_initial_clock_are_rejected(self):
        with self.assertRaises(ValueError):delayed_reference([(0,0),(1,1.8)],-4,7)
        with self.assertRaises(ValueError):delayed_reference([(0,1.8),(3,0)],-4,7)

    def test_ref_centered_coordinates_allow_shared_nearest_feedback_edge(self):
        self.assertEqual(nearest([40],20),20)
        self.assertEqual(nearest([40],60),-20)
        self.assertIsNone(nearest([],60))


if __name__=='__main__':unittest.main()
