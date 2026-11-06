import unittest
from select_selected_target_probe import choose

def point(fine,freq,corner='ss',coarse=47):return dict(controls=dict(fine=fine,coarse=coarse),frequency=dict(frequency_mhz=freq),retained_device_operating_point=dict(corner=corner,supply_v=1.8,temperature_c=27),exterior_bias_operating_point=dict(corner='tt'))

class TargetProbeTest(unittest.TestCase):
    def test_measured_SS_bracket_selects_unassigned_probe(self):
        r=choose([point(120,395.848654405957),point(160,402.60230373881546)])
        self.assertEqual(r['fine'],145);self.assertFalse(r['frequency_assigned'])
    def test_reversed_input_order_is_deterministic(self):
        a,b=point(136,392.43367337905477,'fs',20),point(216,407.19385370006347,'fs',20)
        self.assertEqual(choose([a,b]),choose([b,a]));self.assertEqual(choose([a,b])['fine'],177)
    def test_nonbracket_mixed_geometry_and_nonfinite_rejected(self):
        for a,b in [(point(10,390),point(20,395)),(point(10,390),point(20,410,'fs')),(point(10,390),point(20,float('nan'))),(point(10,410),point(20,390)),(point(10,390),point(10,410))]:
            with self.subTest(a=a,b=b):
                with self.assertRaises(ValueError):choose([a,b])

if __name__=='__main__':unittest.main()
