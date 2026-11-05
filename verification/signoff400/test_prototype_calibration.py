import unittest
from evaluate_prototype_calibration import bracket,evaluate


def point(code,lo,hi,coarse=1):
    return dict(fine_code=code,coarse_code=coarse,minimum_hz=lo,maximum_hz=hi)


class CalibrationControls(unittest.TestCase):
    def test_bracket_allows_a_seed_farther_than_100ppm(self):
        r=bracket([point(8,350e6,370e6),point(128,410e6,430e6),point(247,450e6,470e6)],1,128,True)
        self.assertTrue(r['measured_target_bracket_contains_seed'])
        self.assertFalse(r['calibration_qualified'])
        self.assertFalse(r['capture_under_uncertainty_verified'])

    def test_uncertainty_that_erases_the_bracket_does_not_pass(self):
        r=bracket([point(8,350e6,410e6),point(128,390e6,420e6),point(247,450e6,470e6)],1,128,True)
        self.assertFalse(r['measured_target_bracket_contains_seed'])

    def test_reversed_polarity_and_unmeasured_seed_rejected(self):
        points=[point(8,450e6,470e6),point(128,390e6,410e6),point(247,350e6,370e6)]
        self.assertTrue(bracket(points,1,128,False)['measured_target_bracket_contains_seed'])
        self.assertFalse(bracket(points,1,128,True)['measured_target_bracket_contains_seed'])
        with self.assertRaises(ValueError):bracket(points,1,127,False)
        with self.assertRaises(ValueError):bracket(points+[points[0]],1,128,False)

    def test_single_corner_never_satisfies_five_corner_coverage(self):
        r=evaluate(dict(corners=[dict(corner='tt',temperature_c=27,supply_v=1.8,coarse_code=1,seed=128,increasing=True,
            points=[point(8,350e6,370e6),point(128,390e6,410e6),point(247,450e6,470e6)])]))
        self.assertFalse(r['all_five_measured_brackets_contain_seeds'])
        self.assertFalse(r['release_ready'])


if __name__=='__main__':unittest.main()
