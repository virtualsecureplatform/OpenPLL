import unittest
from fit_prototype_native_timing_surfaces import surface, interval


class TimingSurfaceTests(unittest.TestCase):
    def test_interval_preserves_repeated_native_observations(self):
        points=[(x,y,x+2*y+repeat) for x in (.01,.1,1.) for y in (0,.02,.08) for repeat in (-.003,.007)]
        lo,hi=interval(surface(points),.24,.04)
        self.assertAlmostEqual(lo,.24+2*.04-.003)
        self.assertAlmostEqual(hi,.24+2*.04+.007)

    def test_missing_grid_point_and_extrapolated_holdout_rejected(self):
        points=[(x,y,x+y) for x in (.01,.1,1.) for y in (0,.02,.08)]
        with self.assertRaisesRegex(ValueError,'missing native grid'):
            surface(points[:-1])
        with self.assertRaisesRegex(ValueError,'outside retained axes'):
            interval(surface(points),1.1,.04)

    def test_exact_endpoint_and_signed_delay_preserved(self):
        points=[(x,y,x+y-.2) for x in (.01,.1,1.) for y in (0,.02,.08)]
        self.assertEqual(interval(surface(points),.01,0),(-.19,-.19))


if __name__=='__main__':unittest.main()
