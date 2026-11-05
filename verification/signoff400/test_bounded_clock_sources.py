import bisect,math,unittest
from bounded_clock_sources import simplify,crossings,LEVELS


class BoundedClockTest(unittest.TestCase):
    def test_removes_flat_knots_and_preserves_all_threshold_events(self):
        rows=[(i*1e-12,1.8*min(1,max(0,(i-30)/30))) for i in range(100)]
        reduced,proof=simplify(rows,1e-6)
        self.assertLess(len(reduced),len(rows)/2)
        self.assertEqual(reduced[0],rows[0]);self.assertEqual(reduced[-1],rows[-1])
        self.assertLessEqual(proof['maximum_voltage_difference_V'],1e-6)
        for level in LEVELS:self.assertEqual(crossings(rows,level),crossings(reduced,level))

    def test_sub_bound_threshold_excursions_cannot_be_flattened(self):
        rows=[(0,.8999998),(1,.9000002),(2,.8999998),(3,.9000002),(4,.8999998)]
        reduced,proof=simplify(rows,1e-6)
        self.assertEqual(crossings(rows,.9),crossings(reduced,.9))
        self.assertEqual(len(crossings(reduced,.9)),4)

    def test_voltage_error_bound_includes_curved_and_rippled_regions(self):
        rows=[(i*1e-12,.8+.2*math.sin(i/17)+2e-7*math.sin(i)) for i in range(200)]
        reduced,proof=simplify(rows,1e-6)
        def interp(points,t):
            j=bisect.bisect_right([p[0] for p in points],t)-1
            if j==len(points)-1:return points[-1][1]
            a,v=points[j];b,w=points[j+1];return v+(w-v)*(t-a)/(b-a)
        self.assertTrue(all(abs(interp(rows,t)-interp(reduced,t))<=1e-6+1e-14 for t in [i*1e-13 for i in range(1991)]))
        self.assertFalse(proof['charge_error_bounded']);self.assertFalse(proof['detector_response_equivalence_proven'])

    def test_rejects_unsafe_bound_and_invalid_time_order(self):
        for bound in [0,-1,1e-3,float('nan')]:
            with self.assertRaises(ValueError):simplify([(0,0),(1,1)],bound)
        with self.assertRaises(ValueError):simplify([(0,0),(0,1)],1e-6)


if __name__=='__main__':unittest.main()
