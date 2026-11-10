"""Physical binding must detect errors hidden by primitive multisets."""
import unittest
from native_device_identity import inventory, compare_parameters


def fixture(first='1', second='2'):
    return f'''* OPENPLL_ORIGIN X0 sky130_fd_pr__nfet_01v8 1 2 2 3
X0 d g s b sky130_fd_pr__nfet_01v8 w={first}
* OPENPLL_ORIGIN X1 sky130_fd_pr__nfet_01v8 3 4 4 5
X1 d g s b sky130_fd_pr__nfet_01v8 w={second}
'''


class PhysicalIdentityTests(unittest.TestCase):
    def test_unchanged(self):
        self.assertTrue(compare_parameters(fixture(), fixture())['per_physical_device_parameters_match'])

    def test_swapped_parameters(self):
        self.assertFalse(compare_parameters(fixture(), fixture('2', '1'))['per_physical_device_parameters_match'])

    def test_missing_origin(self):
        with self.assertRaises(ValueError):
            inventory('\n'.join(fixture().splitlines()[1:]))

    def test_duplicate_origin(self):
        with self.assertRaises(ValueError):
            inventory(fixture().replace('3 4 4 5', '1 2 2 3'))


if __name__ == '__main__':
    unittest.main()
