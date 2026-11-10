import unittest
from native_RC_coverage_v2 import assess

REFERENCE = '.subckt p VGND d\nX0 d g VGND VGND sky130_fd_pr__nfet_01v8 w=1\n.ends p\n'
MARKERS = 'subcap "wellRoot" -0\nsubcap "d" -0\n'
ALIASES = 'equiv "wellRoot" "VGND"\n'


class OriginalConductorCoverage(unittest.TestCase):
    def test_original_substrate_alias(self):
        self.assertTrue(assess(REFERENCE, MARKERS, ALIASES)['device_and_port_output_coverage_verified'])

    def test_unproven_alias_rejected(self):
        self.assertFalse(assess(REFERENCE, MARKERS, '')['device_and_port_output_coverage_verified'])

    def test_duplicate_alias_output_rejected(self):
        self.assertFalse(assess(REFERENCE, MARKERS + 'subcap "VGND" -0\n', ALIASES)['device_and_port_output_coverage_verified'])

    def test_malformed_alias_rejected(self):
        with self.assertRaises(ValueError):
            assess(REFERENCE, MARKERS, 'equiv "wellRoot"\n')


if __name__ == '__main__':
    unittest.main()
