import unittest
from prototype_physical_domain_windows import native_key


class NativePlacementKeys(unittest.TestCase):
    def test_reflection_and_exact_grid(self):
        self.assertEqual(native_key(['cell', 1, 0, 20, 0, -1, 30], 5),
                         ('cell', (1, 0, 100, 0, -1, 150)))
        self.assertEqual(native_key(['cell', 0, -1, 20, 1, 0, 30], 5),
                         ('cell', (0, -1, 100, 1, 0, 150)))
        with self.assertRaises(ValueError):
            native_key(['cell', 1, 1, 20, 0, 1, 30], 5)


if __name__ == '__main__':
    unittest.main()
