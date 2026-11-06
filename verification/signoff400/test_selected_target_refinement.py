import unittest
from select_selected_target_probe_v2 import plan

def point(fine,freq,corner='fs',coarse=20):return dict(case=f'{corner}_{fine}',controls=dict(fine=fine,coarse=coarse),frequency=dict(frequency_mhz=freq),retained_device_operating_point=dict(corner=corner,supply_v=1.8,temperature_c=27),exterior_bias_operating_point=dict(corner='tt'))

class TargetRefinementTest(unittest.TestCase):
    def test_FS_narrows_to_measured_nearest_bracket(self):
        r=plan([point(136,392.43367337905477),point(177,399.4912571419811),point(216,407.19385370006347)])
        self.assertEqual(r['requested_probe']['fine'],180);self.assertEqual(r['endpoint_cases'],['fs_177','fs_216']);self.assertFalse(r['frequency_assigned'])
    def test_SS_measured_target_avoids_unnecessary_probe(self):
        r=plan([point(120,395.848654405957,'ss',47),point(145,400.03682389232654,'ss',47),point(160,402.60230373881546,'ss',47)])
        self.assertEqual(r['action'],'retain_measured_conditional_target');self.assertIsNone(r['requested_probe']);self.assertAlmostEqual(r['nominal_error_ppm'],92.059730816,places=6)
    def test_no_extrapolation_or_nonmonotonic_curve(self):
        for rows in [[point(10,390),point(20,395)],[point(10,410),point(20,390)],[point(10,390),point(10,410)]]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):plan(rows)
    def test_mixed_operating_points_rejected_before_retaining_target(self):
        with self.assertRaises(ValueError):plan([point(10,399.99),point(20,410,'ss')])

if __name__=='__main__':unittest.main()
