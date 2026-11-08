import unittest
from audit_keeper_R_terminal_renaming import compare


class TerminalRenaming(unittest.TestCase):
    before = 'X1 t0 gate g g sky130_fd_pr__nfet_01v8 w=1 l=.15\nR1 root n 1\nR2 n t0 2\nR3 n t0 3\n'
    after = before.replace('t0', 't8')

    def test_terminal_renaming_and_parallel_R_preserved(self):
        result = compare(self.before, self.after)
        self.assertTrue(result['exact_R_multigraph_match_under_terminal_mapping'])
        self.assertEqual(result['renamed_terminal_nodes'], {'t0': 't8'})
        self.assertFalse(result['cap_placement_compared'])

    def test_changed_R_value_detected(self):
        result = compare(self.before, self.after.replace('n t8 3', 'n t8 4'))
        self.assertFalse(result['exact_R_multigraph_match_under_terminal_mapping'])

    def test_external_terminal_change_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.before, self.after.replace(' gate ', ' wrong '))


if __name__ == '__main__':
    unittest.main()
