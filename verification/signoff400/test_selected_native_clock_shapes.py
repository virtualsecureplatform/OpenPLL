import unittest
from selected_native_clock_shapes import shift_window,rising

class NativeClockShapeTests(unittest.TestCase):
    def test_translation_preserves_knots_and_pwl_boundary_values(self):
        rows=[(0,0),(1,0),(2,1.8),(3,1.8),(4,0)]
        result=shift_window(rows,.5,3)
        self.assertEqual(result,[(0,0),(0.5,0),(1.5,1.8),(2.5,1.8),(3,.9)])
        self.assertEqual(rising(result,0),rising(rows,0)-.5)
    def test_extrapolation_is_rejected(self):
        for shift,duration in [(-1,1),(0,3)]:
            with self.assertRaises(ValueError):shift_window([(0,0),(2,1.8)],shift,duration)
    def test_selects_first_rise_after_release(self):
        self.assertEqual(rising([(0,0),(1,1.8),(2,0),(3,1.8)],1),2.5)

if __name__=='__main__':unittest.main()
