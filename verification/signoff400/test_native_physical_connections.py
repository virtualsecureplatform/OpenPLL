import unittest
from native_physical_connections import assess


def fixture(swapped=False):
    drains = ['e', 'd'] if swapped else ['d', 'e']
    return '\n'.join(f'* OPENPLL_ORIGIN X{i} sky130_fd_pr__nfet_01v8 {i*2} 0 {i*2+1} 1\nX{i} {d} g s b sky130_fd_pr__nfet_01v8 w=1' for i, d in enumerate(drains))


class ConnectionTests(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(assess(fixture(), fixture())['per_physical_device_connections_verified'])

    def test_swapped_devices(self):
        self.assertFalse(assess(fixture(), fixture(True))['per_physical_device_connections_verified'])

    def test_split_terminal(self):
        candidate = fixture().replace('X0 d ', 'X0 internal ') + '\nR0 d internal 1'
        self.assertTrue(assess(fixture(), candidate)['per_physical_device_connections_verified'])

    def test_wire_short(self):
        self.assertFalse(assess(fixture(), fixture() + '\nR0 d e 1')['per_physical_device_connections_verified'])


if __name__ == '__main__':
    unittest.main()
