import unittest
from review_prototype_observed_capture_resolution_v2 import resolution

class CaptureResolution(unittest.TestCase):
    def samples(self,output):
        return [[i*.5e-9,0,output(i*.5),0,0] for i in range(61)]
    def test_either_stable_rail_is_accepted_and_last_excursion_counts(self):
        cases=[dict(kind='data_rise',offset_ps=0)]
        r,_=resolution(self.samples(lambda t:0),cases)
        self.assertEqual(r[0]['observed_final_rail'],0)
        self.assertEqual(r[0]['observed_resolution_upper_ns_from_test_edge'],0)
        r,_=resolution(self.samples(lambda t:0 if t<20 else .9 if t<21 else 1.8),cases)
        self.assertEqual(r[0]['observed_final_rail'],1)
        self.assertAlmostEqual(r[0]['observed_resolution_upper_ns_from_test_edge'],1.)
    def test_persistent_midrail_never_becomes_a_resolution_pass(self):
        r,_=resolution(self.samples(lambda t:.9 if t>=20 else 0),[dict(kind='data_rise',offset_ps=0)])
        self.assertIsNone(r[0]['observed_final_rail'])
        self.assertIsNone(r[0]['observed_resolution_upper_ns_from_test_edge'])

if __name__=='__main__':unittest.main()
