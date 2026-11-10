import unittest
from prepare_keeper_native_RC_1695 import normalize


class LiteralRCTests(unittest.TestCase):
    def test_signed_and_zero_branches(self):
        source = '.subckt t a b\nR0 a internal 1e-6\nR1 internal b 0\nC0 internal b -1e-40\nC1 a b 0\n.ends t\n'
        model, nodes, metrics = normalize(source)
        self.assertTrue(metrics['all_RC_endpoints_and_literal_values_preserved'])
        self.assertEqual(metrics['literal_RC_branches_preserved'], 4)
        expected = {'R0': ('a', nodes['internal'], '1e-6'),
                    'R1': (nodes['internal'], 'b', '0'),
                    'C0': (nodes['internal'], 'b', '-1e-40'),
                    'C1': ('a', 'b', '0')}
        actual = {f[0]: tuple(f[1:]) for line in model.splitlines()
                  if (f := line.split()) and f[0] in expected}
        self.assertEqual(actual, expected)

    def test_negative_wire_rejected(self):
        with self.assertRaises(ValueError):
            normalize('.subckt t a b\nR0 a b -1\n.ends t\n')

    def test_duplicate_branch_rejected(self):
        with self.assertRaises(ValueError):
            normalize('.subckt t a b\nC0 a b 1\nC0 a b 2\n.ends t\n')

    def test_case_colliding_conductors_rejected(self):
        with self.assertRaises(ValueError):
            normalize('.subckt t a b\nC0 a internal 1\nR0 INTERNAL b 1\n.ends t\n')


if __name__ == '__main__':
    unittest.main()
