import unittest
from select_measured_target_refinement import choose

def point(code,hz):return dict(coarse=20,fine=code,frequency_hz=hz)

class MeasuredTargetRefinement(unittest.TestCase):
    def test_secant_target_instead_of_bracket_midpoint(self):
        r=choose([point(133,397235125.183),point(165,404e6)])
        self.assertEqual(r['fine'],146);self.assertEqual(r['bracket_codes'],[133,165])
        self.assertFalse(r['predicted_frequency_assigned']);self.assertNotIn('frequency_hz',r)
    def test_measured_in_band_point_skips_extra_native_work(self):
        r=choose([point(133,397e6),point(146,400.03e6),point(165,404e6)])
        self.assertEqual(r['state'],'measured_nominal_target_observed');self.assertNotIn('fine',r)
        self.assertFalse(r['target_bracket_and_startup_headroom_qualified'])
    def test_exact_acceptance_boundaries_skip_unnecessary_run(self):
        for hz in (399600000,400400000):
            self.assertEqual(choose([point(146,hz)])['state'],'measured_nominal_target_observed')
        self.assertEqual(choose([point(146,399599999)])['state'],'measurement_needed')
    def test_unreachable_adjacent_bracket_does_not_invent_code(self):
        r=choose([point(145,399e6),point(146,401e6)])
        self.assertEqual(r['state'],'adjacent_target_bracket_requires_review');self.assertNotIn('fine',r)
    def test_bad_curve_rejected_before_in_band_shortcut(self):
        for rows in ([point(10,400e6),point(10,401e6)],[point(10,400e6),point(20,399e6)],[point(10,float('nan'))]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):choose(rows)
    def test_unbracketed_hint_only_requests_a_new_native_point(self):
        r=choose([point(111,392.31e6),point(112,392.67e6),point(133,397.235e6)])
        self.assertEqual(r['state'],'measurement_needed');self.assertGreater(r['fine'],133)
        self.assertFalse(r['predicted_frequency_assigned'])

if __name__=='__main__':unittest.main()
