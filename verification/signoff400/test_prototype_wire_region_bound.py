import unittest
from bound_prototype_wire_region import envelope


class WireEnvelope(unittest.TestCase):
    def test_width_and_endpoint_extension(self):
        box, radius = envelope([(10, 20), (100, 20)], [3, 10], [12], [], [])
        self.assertEqual(radius, 12)
        self.assertEqual(box, [-2, 8, 112, 32])

    def test_rotated_via_and_absolute_patch_are_enclosed(self):
        box, radius = envelope([(10, 20), (100, 20)], [2], [], [[-3, -4, 3, 4]], [[-20, 15, 10, 30]])
        self.assertEqual(radius, 7)
        self.assertEqual(box, [-20, 13, 107, 30])
        for dx, dy in ((-3, -4), (-3, 4), (3, -4), (3, 4)):
            for x, y in ((dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)):
                self.assertLessEqual(abs(x), radius)
                self.assertLessEqual(abs(y), radius)

    def test_missing_and_invalid_geometry_rejected(self):
        for args in (([], [2], [], [], []), ([(0, 0)], [0], [], [], []),
                     ([(0, 0)], [2], [-1], [], []), ([(0, 0)], [2], [], [[2, 0, 1, 1]], [])):
            with self.assertRaises(ValueError):
                envelope(*args)


if __name__ == '__main__':
    unittest.main()
