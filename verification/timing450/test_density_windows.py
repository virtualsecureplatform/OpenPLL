import unittest
from characterize_density import origins


class DensityWindows(unittest.TestCase):
    def test_overlap_grid_and_exact_window(self):
        self.assertEqual(origins(0, 100, 50, 25), [0, 25, 50])
        self.assertEqual(origins(-25, 25, 50, 25), [-25])

    def test_outside_geometry_is_not_invented(self):
        self.assertEqual(origins(0, 450, 700, 70), [])
        self.assertEqual(origins(0, 101, 50, 25), [0, 25, 50])

    def test_invalid_dimensions_rejected(self):
        for args in ((0, 0, 50, 25), (0, 100, 0, 25), (0, 100, 50, 0)):
            with self.assertRaises(RuntimeError):
                origins(*args)


if __name__ == '__main__':
    unittest.main()
