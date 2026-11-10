import unittest
from native_wire_values import assess


class NativeWireTests(unittest.TestCase):
    def test_exact_and_scale(self):
        self.assertTrue(assess('scale 1000 1 1\nresist "a" "b" 4.975',
                               'R0 a b 4.975')['per_native_wire_resistance_values_verified'])

    def test_rounding_bias(self):
        self.assertFalse(assess('scale 1000 1 1\nresist "a" "b" .000001',
                                'R0 a b .000501')['per_native_wire_resistance_values_verified'])

    def test_zero(self):
        self.assertFalse(assess('scale 1000 1 1\nresist "a" "b" 0',
                                'R0 a b 1e-40')['per_native_wire_resistance_values_verified'])

    def test_missing_parallel_branch(self):
        self.assertFalse(assess('scale 1000 1 1\nresist "a" "b" 1\nresist "a" "b" 1',
                                'R0 a b 1')['per_native_wire_resistance_values_verified'])


if __name__ == '__main__':
    unittest.main()
