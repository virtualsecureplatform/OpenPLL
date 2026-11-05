import unittest
from select_calibration_point import choose

def point(c,f):return dict(coarse=20,fine=c,frequency_hz=f*1e6)
class SelectionTests(unittest.TestCase):
    def test_first_missing_neighbor(self):self.assertEqual(choose([point(111,392.31)])['fine'],112)
    def test_negative_direction(self):self.assertLess(choose([point(111,392),point(112,391)])['fine'],111)
    def test_positive_direction_does_not_measure_every_code(self):self.assertGreater(choose([point(111,392),point(112,393)])['fine'],112)
    def test_native_holdout_inside_bracket(self):self.assertEqual(choose([point(111,392),point(119,408)])['fine'],115)
    def test_adjacent_bracket_is_not_qualification(self):
        a=choose([point(111,399),point(112,401)]);self.assertEqual(a['state'],'target_bracket_observed');self.assertFalse(a['uncertainty_qualified'])
    def test_clips_measurement_location_to_safe_codes(self):self.assertEqual(choose([point(111,392),point(112,392.0001)])['fine'],247)
    def test_rejects_duplicate_data(self):
        with self.assertRaises(ValueError):choose([point(111,392),point(111,393)])
if __name__=='__main__':unittest.main()
