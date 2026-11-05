import unittest
from compare_prototype_C_placement_pilots import compare


class PlacementComparison(unittest.TestCase):
    def point(self, frequency):
        return dict(corner='tt',temperature_c=27,supply_v=1.8,coarse_code=20,fine_code=111,
                    measurement_start_s=20e-9,measurement_end_s=80e-9,
                    average_frequency_hz=frequency,complete_measured_cycles=20)

    def test_observed_sensitivity_is_not_a_physical_uncertainty_bound(self):
        r=compare(self.point(400e6),self.point(404e6))
        self.assertAlmostEqual(r['observed_frequency_difference_ppm'],10000)
        self.assertFalse(r['physical_placement_uncertainty_bound_established'])
        self.assertFalse(r['release_ready'])

    def test_mismatched_points_invalid_frequency_and_insufficient_cycles_rejected(self):
        for field,value in [('corner','ss'),('fine_code',112),('average_frequency_hz',float('nan')),('complete_measured_cycles',2)]:
            b=self.point(400e6);b[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compare(self.point(400e6),b)


if __name__=='__main__':unittest.main()
