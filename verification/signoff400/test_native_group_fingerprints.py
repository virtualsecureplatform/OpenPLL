"""Pointer reuse, topology mutations and ambiguous labels in native diagnostics."""
import unittest
from audit_native_groups import groups


def fixture(group, prefix, resistance='2', node_name='B'):
    return [f'BEGIN {group} "NET"\n',
            f'NODE {group} {prefix}a "A" 0 0 1 0\n',
            f'EDGE {group} {prefix}a {prefix}a {prefix}b {resistance} 2 512\n',
            f'NODE {group} {prefix}b "{node_name}" 0 0 1 0\n',
            f'EDGE {group} {prefix}b {prefix}a {prefix}b {resistance} 2 512\n',
            f'END {group}\n']


class NativeGroupFingerprints(unittest.TestCase):
    def test_equivalent_groups_ignore_only_pointers_and_group_identity(self):
        rows = list(groups(fixture(1, 'old') + fixture(2, 'new')))
        self.assertEqual(rows[0]['fingerprint'], rows[1]['fingerprint'])
        self.assertNotEqual(rows[0]['native_group_id'], rows[1]['native_group_id'])
        self.assertEqual(rows[0]['nodes'], 2)
        self.assertEqual(rows[0]['incident_edges'], 2)

    def test_native_value_and_incidence_multiplicity_are_preserved(self):
        base = list(groups(fixture(1, 'p')))[0]['fingerprint']
        changed = list(groups(fixture(2, 'p', resistance='3')))[0]['fingerprint']
        self.assertNotEqual(base, changed)
        rows = fixture(3, 'p')
        rows.insert(-1, rows[-2])
        self.assertNotEqual(base, list(groups(rows))[0]['fingerprint'])

    def test_ambiguous_labels_and_corrupt_groups_never_prove_equivalence(self):
        ambiguous = list(groups(fixture(1, 'p', node_name='A')))[0]
        self.assertTrue(ambiguous['ambiguous_node_labels'])
        self.assertIsNone(ambiguous['fingerprint'])
        for rows in (fixture(1, 'p')[:-1], fixture(1, 'p') + fixture(1, 'q'),
                     ['EDGE 1 a a b 2 2 512\n']):
            with self.assertRaises(ValueError):
                list(groups(rows))


if __name__ == '__main__':
    unittest.main()
