import unittest
from magic_fringe_kernel import measure, LEFT, RIGHT, TOP, BOTTOM


class FringeKernelTests(unittest.TestCase):
    def test_rectangle_partition_conserves_weight(self):
        boundary = [0, 0, 0, 20]
        whole = measure([5, 0, 55, 20], boundary, RIGHT, 0.02)
        pieces = [[5, 0, 20, 7], [20, 0, 55, 7], [5, 7, 40, 20], [40, 7, 55, 20]]
        self.assertAlmostEqual(sum(measure(r, boundary, RIGHT, 0.02) for r in pieces), whole, places=13)

    def test_mirrored_directions_have_equal_weight(self):
        expected = measure([5, 0, 55, 20], [0, 0, 0, 20], RIGHT, 0.02)
        for box, boundary, direction in [([-55, 0, -5, 20], [0, 0, 0, 20], LEFT),
                                         ([0, 5, 20, 55], [0, 0, 20, 0], TOP),
                                         ([0, -55, 20, -5], [0, 0, 20, 0], BOTTOM)]:
            self.assertEqual(measure(box, boundary, direction, 0.02), expected)

    def test_equal_area_farther_from_edge_has_less_weight(self):
        boundary = [0, 0, 0, 20]
        self.assertGreater(measure([5, 0, 25, 20], boundary, RIGHT, 0.02),
                           measure([35, 0, 55, 20], boundary, RIGHT, 0.02))

    def test_matches_independent_density_quadrature(self):
        n = 1000
        h = 50 / n
        def density(x):
            return 20 * 0.6366 * 0.02 / (1 + (0.02 * x) ** 2)
        integral = h / 3 * (density(5) + density(55)
                            + sum((4 if i % 2 else 2) * density(5 + i * h) for i in range(1, n)))
        self.assertAlmostEqual(measure([5, 0, 55, 20], [0, 0, 0, 20], RIGHT, 0.02), integral, places=11)


if __name__ == '__main__':
    unittest.main()
