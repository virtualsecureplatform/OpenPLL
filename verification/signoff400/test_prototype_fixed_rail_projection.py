import unittest
from fractions import Fraction as F
from project_prototype_fixed_rail_C import FIXED, project


class ProjectionTests(unittest.TestCase):
    def test_signed_compensation_is_aggregated_without_clipping(self):
        pairs = {('a', 'VPWR'): F(3, 10), ('VGND', 'a'): F(-1, 10),
                 ('VPWR', 'VGND'): F(-100), ('a', 'b'): F(-1, 20)}
        self.assertEqual(project(pairs, {'VPWR', 'VGND'}),
                         {(FIXED, 'a'): F(1, 5), ('a', 'b'): F(-1, 20)})

    def test_exact_energy_for_arbitrary_dynamic_voltages(self):
        pairs = {('a', 'VPWR'): F(3, 7), ('VGND', 'a'): F(-1, 13),
                 ('VPWR', 'VGND'): F(-100), ('a', 'b'): F(5, 17),
                 ('VPB', 'b'): F(1, 19)}
        dynamic = project(pairs, {'VPWR', 'VGND', 'VPB'})
        for a in range(-3, 4):
            for b in range(-3, 4):
                # All ideal supplies have zero small-signal voltage, regardless
                # of their different DC biases.
                voltage = dict(a=F(a, 11), b=F(b, 23), VPWR=0, VGND=0, VPB=0)
                expected = sum(c * (voltage[x] - voltage[y])**2
                               for (x, y), c in pairs.items())
                voltage[FIXED] = 0
                actual = sum(c * (voltage[x] - voltage[y])**2
                             for (x, y), c in dynamic.items())
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
