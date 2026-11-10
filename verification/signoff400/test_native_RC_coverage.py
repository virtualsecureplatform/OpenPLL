import unittest
from native_RC_coverage import assess

REFERENCE = '''.subckt probe p
X0 d g s b sky130_fd_pr__nfet_01v8 w=1
C0 fill 0 1e-18
.ends
'''
MARKERS = '\n'.join('subcap "' + n + '" -0' for n in ['p', 'd', 's'])


class CoverageTests(unittest.TestCase):
    def test_classifies_undriven_populations(self):
        result = assess(REFERENCE, MARKERS)
        self.assertTrue(result['device_and_port_output_coverage_verified'])
        self.assertEqual(result['gate_only_without_output'], ['g'])
        self.assertEqual(result['bulk_only_without_output'], ['b'])
        self.assertEqual(result['capacitance_only_without_output_count'], 1)

    def test_missing_active_network(self):
        self.assertFalse(assess(REFERENCE, MARKERS.replace('subcap "d" -0', ''))['device_and_port_output_coverage_verified'])

    def test_alias_resolves(self):
        self.assertTrue(assess(REFERENCE + 'R0 d alias 0\n', MARKERS.replace('"d"', '"alias"'))['device_and_port_output_coverage_verified'])

    def test_duplicate_alias_output(self):
        self.assertFalse(assess(REFERENCE + 'R0 d alias 0\n', MARKERS + '\nsubcap "alias" -0')['device_and_port_output_coverage_verified'])


if __name__ == '__main__':
    unittest.main()
